from django.urls import path

from apps.humming import views

urlpatterns = [
    path('', views.HummingJobListCreateView.as_view(), name='humming-list-create'),
    path('callback/', views.HummingCallbackView.as_view(), name='humming-callback'),
    path('<uuid:pk>/', views.HummingJobDetailView.as_view(), name='humming-detail'),
    path('<uuid:pk>/choose/', views.HummingChooseView.as_view(), name='humming-choose'),
]
