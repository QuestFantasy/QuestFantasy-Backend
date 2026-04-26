from django.urls import path

from .views import PlayerGoldView, PlayerInventoryView, PlayerProfileView


urlpatterns = [
    path('profile/', PlayerProfileView.as_view(), name='player-profile'),
    path('inventory/', PlayerInventoryView.as_view(), name='player-inventory'),
    path('gold/', PlayerGoldView.as_view(), name='player-gold'),
]
