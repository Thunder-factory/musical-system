from __future__ import annotations

import secrets
import string
import time

from django.db import transaction
from firebase_admin import db

from apps.credits.services.credit_service import check_balance, deduct_credits
from apps.karaoke.models import KaraokeTrack, UserKaraokeAccess
from apps.notifications.firebase import get_firebase_app
from apps.users.models import User
from ml.modal_client import get_presigned_url

ROOM_COST = 1
ROOM_CODE_LENGTH = 8


class RoomError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _database_app():
    try:
        app = get_firebase_app()
    except Exception as exc:
        raise RoomError('Firebase no está configurado.', 503) from exc
    if app is None:
        raise RoomError('Firebase no está configurado.', 503)
    return app


def _room_reference(code: str):
    app = _database_app()
    return db.reference(f'karaokeRooms/{code}', app=app)


def _generate_room_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(ROOM_CODE_LENGTH))


def _new_room_code() -> str:
    for _ in range(10):
        code = _generate_room_code()
        if _room_reference(code).get() is None:
            return code
    raise RoomError('No se pudo generar un código de sala disponible.', 503)


def _find_active_room(user_id: str, karaoke_id: str) -> str | None:
    rooms = (
        db.reference('karaokeRooms', app=_database_app())
        .order_by_child('hostId')
        .equal_to(str(user_id))
        .get()
        or {}
    )

    for room_code, room in rooms.items():
        if (
            isinstance(room, dict)
            and room.get('karaokeId') == str(karaoke_id)
            and room.get('state') in {'waiting', 'playing'}
        ):
            return room_code

    return None


def create_room(user: User, karaoke_id: str) -> dict:
    try:
        track = KaraokeTrack.objects.select_related('song').get(id=karaoke_id)
    except KaraokeTrack.DoesNotExist as exc:
        raise RoomError('Karaoke no encontrado.', 404) from exc

    if track.status != 'ready':
        raise RoomError('El karaoke todavía no está listo.', 409)

    if not track.instrumental_s3_key:
        raise RoomError('El audio instrumental no está disponible.', 409)

    if not UserKaraokeAccess.objects.filter(user=user, karaoke_track=track).exists():
        raise RoomError('No tenés acceso a este karaoke.', 403)

    room_reference = None
    try:
        with transaction.atomic():
            locked_user = User.objects.select_for_update().get(pk=user.pk)
            existing_room_code = _find_active_room(locked_user.pk, track.id)
            if existing_room_code:
                return {
                    'room_code': existing_room_code,
                    'credit_balance': locked_user.credit_balance,
                }

            if not check_balance(locked_user, required=ROOM_COST):
                raise RoomError('No tenés créditos suficientes para crear una sala.', 402)

            room_code = _new_room_code()
            room_reference = _room_reference(room_code)
            room_data = {
                'roomCode': room_code,
                'hostId': str(locked_user.pk),
                'hostName': locked_user.full_name,
                'songId': str(track.song_id),
                'songTitle': track.song.title,
                'karaokeId': str(track.id),
                'playUrl': get_presigned_url(
                    track.instrumental_s3_key,
                    expiry_seconds=3600,
                ),
                'lyricsTimestamps': track.lyrics_timestamps or [],
                'state': 'waiting',
                'currentTime': 0,
                'startedAt': None,
                'participants': {
                    str(locked_user.pk): {
                        'userId': str(locked_user.pk),
                        'userName': locked_user.full_name,
                        'joinedAt': time.time_ns() // 1_000_000,
                    }
                },
                'creditsCharged': ROOM_COST,
            }

            room_reference.set(room_data)

            deduct_credits(
                locked_user,
                ROOM_COST,
                reference_id=room_code,
                reference_type='karaoke_room',
            )
    except Exception:
        if room_reference is not None:
            try:
                room_reference.delete()
            except Exception:
                pass
        raise

    return {
        'room_code': room_code,
        'credit_balance': locked_user.credit_balance,
    }


def join_room(user: User, room_code: str) -> dict:
    code = room_code.strip().upper()
    if not code:
        raise RoomError('El código de sala es obligatorio.', 400)

    room_reference = _room_reference(code)
    room = room_reference.get()
    if not room:
        raise RoomError('Sala no encontrada.', 404)
    if room.get('state') == 'ended':
        raise RoomError('La sala ya terminó.', 409)

    participant = {
        'userId': str(user.pk),
        'userName': user.full_name,
        'joinedAt': time.time_ns() // 1_000_000,
    }
    room_reference.update({f'participants/{user.pk}': participant})

    return {
        'room_code': code,
        'joined': True,
        'is_host': str(room.get('hostId')) == str(user.pk),
    }
