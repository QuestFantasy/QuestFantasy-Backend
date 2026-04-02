"""URL configuration for authentication and health check endpoints."""
from django.urls import path

from .views import LoginView, LogoutView, ProfileView, RegisterView
from .health import HealthCheckView, DatabaseHealthCheckView, ReadinessCheckView

urlpatterns = [
    # Authentication endpoints
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', ProfileView.as_view(), name='profile'),
    # Health check endpoints
    path('health/', HealthCheckView.as_view(), name='health'),
    path('health/db/', DatabaseHealthCheckView.as_view(), name='health-db'),
    path('health/ready/', ReadinessCheckView.as_view(), name='health-ready'),
]

