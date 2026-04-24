"""Main URL configuration for QuestFantasy backend."""
from django.contrib import admin
from django.urls import include, path

from accounts.health import HealthCheckView

urlpatterns = [
    path('admin/', admin.site.urls),
    # Global health check (no authentication required)
    path('health/', HealthCheckView.as_view(), name='health-global'),
    # API routes
    path('api/auth/', include('accounts.urls')),
    path('api/player/', include('game_data.urls')),
]

