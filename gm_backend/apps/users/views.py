from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.serializers import (
    LoginSerializer,
    RegisterSerializer,
    UserProfileSerializer,
    UserProfileUpdateSerializer,
)


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
        """Guarda o actualiza el token FCM del usuario."""
        token = request.data.get('fcm_token')
        if not token:
            return Response({'detail': 'Token requerido.'}, status=status.HTTP_400_BAD_REQUEST)
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
