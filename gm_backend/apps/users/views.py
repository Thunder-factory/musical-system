from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from django.db import transaction

from apps.users.serializers import (
    LoginSerializer,
    RegisterSerializer,
    UserProfileSerializer,
    UserProfileUpdateSerializer,
)
from apps.users.models import UserDevice


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserProfileSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserProfileSerializer(request.user).data)

    def patch(self, request):
        serializer = UserProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserProfileSerializer(request.user).data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            token = RefreshToken(request.data.get("refresh"))
            token.blacklist()
        except Exception:
            pass
        device_id = str(request.data.get('device_id') or '').strip()
        fcm_token = str(request.data.get('fcm_token') or '').strip()
        devices = UserDevice.objects.filter(user=request.user, is_active=True)
        if device_id:
            device_tokens = set(
                devices.filter(device_id=device_id).values_list('token', flat=True)
            )
            devices.filter(device_id=device_id).update(is_active=False)
            if request.user.fcm_token in device_tokens:
                request.user.fcm_token = None
                request.user.save(update_fields=['fcm_token'])
        elif fcm_token:
            devices.filter(token=fcm_token).update(is_active=False)
            if request.user.fcm_token == fcm_token:
                request.user.fcm_token = None
                request.user.save(update_fields=['fcm_token'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")
        if not user.check_password(old_password):
            return Response(
                {"detail": "Contraseña actual incorrecta."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(new_password)
        user.save()
        return Response({"detail": "Contraseña actualizada."})


class FCMTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Retorna el token FCM del usuario autenticado."""
        return Response({'fcm_token': request.user.fcm_token})

    def post(self, request):
        """Registra un token FCM y lo asocia con un dispositivo."""
        token = request.data.get('fcm_token')
        if not isinstance(token, str):
            return Response({'detail': 'Token requerido.'}, status=status.HTTP_400_BAD_REQUEST)
        token = token.strip()
        if not token or len(token) > 4096:
            return Response({'detail': 'Token FCM inválido.'}, status=status.HTTP_400_BAD_REQUEST)

        platform = str(request.data.get('platform') or 'unknown').strip().lower()
        if platform not in dict(UserDevice.PLATFORM_CHOICES):
            return Response({'detail': 'Plataforma inválida.'}, status=status.HTTP_400_BAD_REQUEST)
        device_id = str(request.data.get('device_id') or '').strip()[:255]

        with transaction.atomic():
            if device_id:
                UserDevice.objects.filter(
                    user=request.user,
                    device_id=device_id,
                ).exclude(token=token).update(is_active=False)

            device = UserDevice.objects.select_for_update().filter(token=token).first()
            if device is None:
                device = UserDevice(user=request.user, token=token)
            elif device.user_id != request.user.id:
                # Un token FCM solo puede tener un propietario activo.
                type(request.user).objects.filter(
                    pk=device.user_id,
                    fcm_token=token,
                ).update(fcm_token=None)
                device.user = request.user

            device.platform = platform
            device.device_id = device_id
            device.is_active = True
            device.last_seen_at = timezone.now()
            device.save()

            # Compatibilidad con clientes anteriores que todavía leen User.fcm_token.
            request.user.fcm_token = token
            request.user.save(update_fields=['fcm_token'])
        return Response({'detail': 'Token guardado.'})


class FirebaseCustomTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from firebase_admin import auth
        from apps.notifications.firebase import get_firebase_app

        try:
            firebase_app = get_firebase_app()
            token = auth.create_custom_token(
                uid=str(request.user.pk),
                app=firebase_app,
            )
            return Response({
                'firebase_token': token.decode('utf-8'),
            })
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                'No se pudo generar el Firebase Custom Token'
            )
            return Response(
                {'detail': 'No se pudo iniciar la sesión de Firebase.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
