import logging

import firebase_admin
from django.conf import settings
from firebase_admin import credentials, messaging

logger = logging.getLogger(__name__)


def get_firebase_app():
    app = firebase_admin.get_app() if firebase_admin._apps else None

    if app is not None:
        return app

    private_key = settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n")

    if not all([
        settings.FIREBASE_PROJECT_ID,
        settings.FIREBASE_CLIENT_EMAIL,
        private_key,
    ]):
        raise RuntimeError(
            "Faltan credenciales de Firebase Admin."
        )

    certificate = {
        "type": "service_account",
        "project_id": settings.FIREBASE_PROJECT_ID,
        "client_email": settings.FIREBASE_CLIENT_EMAIL,
        "private_key": private_key,
        "token_uri": "https://oauth2.googleapis.com/token",
    }

    cred = credentials.Certificate(certificate)

    options = {"projectId": settings.FIREBASE_PROJECT_ID}
    if settings.FIREBASE_DATABASE_URL:
        options["databaseURL"] = settings.FIREBASE_DATABASE_URL

    return firebase_admin.initialize_app(cred, options)


def send_push(
    token: str,
    title: str,
    body: str,
    data: dict | None = None,
):
    if not settings.PUSH_NOTIFICATIONS_ENABLED:
        logger.debug(
            "Notificaciones push deshabilitadas."
        )
        return None

    app = get_firebase_app()

    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=data or {},
        token=token,
    )

    return messaging.send(message, app=app)
