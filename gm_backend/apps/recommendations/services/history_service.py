from apps.recommendations.models import ListeningHistory
from django.db.models import F
from django.utils import timezone

def update_listening_history(user, song, duration_seconds: int = 0):
    """
    Llamar desde community.record_play() cada vez que alguien escucha una canción.
    Actualiza el historial agregado por tag.
    """
    duration_seconds = max(0, int(duration_seconds or 0))
    for tag in song.tags.all():
        history, _ = ListeningHistory.objects.get_or_create(
            user=user, tag=tag,
            defaults={'play_count': 0, 'total_seconds': 0}
        )
        ListeningHistory.objects.filter(pk=history.pk).update(
            play_count=F('play_count') + 1,
            total_seconds=F('total_seconds') + duration_seconds,
            last_played_at=timezone.now(),
            updated_at=timezone.now(),
        )

    from apps.recommendations.services.profile_service import recalculate_profile
    return recalculate_profile(user)
