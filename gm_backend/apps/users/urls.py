from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from apps.users.views import (
    RegisterView,
    LoginView,
    MeView,
    ChangePasswordView,
    LogoutView,
    FCMTokenView,
    FirebaseCustomTokenView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth-register'),
    path('login/', LoginView.as_view(), name='auth-login'),
    path('refresh/', TokenRefreshView.as_view(), name='auth-refresh'),
    path('me/', MeView.as_view(), name='auth-me'),
    path('logout/', LogoutView.as_view(), name='auth-logout'),
    path('change-password/', ChangePasswordView.as_view(), name='auth-change-password'),
    path('fcm-token/', FCMTokenView.as_view(), name='fcm-token'),
    path('firebase-token/', FirebaseCustomTokenView.as_view(), name='firebase-custom-token'),
]
