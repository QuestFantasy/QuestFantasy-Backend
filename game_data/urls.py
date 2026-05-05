from django.urls import path

from .views import (
    MarketplaceDetailView,
    MarketplaceListView,
    MarketplacePurchaseView,
    PlayerGoldView,
    PlayerInventoryView,
    PlayerProfileView,
)


urlpatterns = [
    path('profile/', PlayerProfileView.as_view(), name='player-profile'),
    path('inventory/', PlayerInventoryView.as_view(), name='player-inventory'),
    path('gold/', PlayerGoldView.as_view(), name='player-gold'),
    # Marketplace
    path('marketplace/', MarketplaceListView.as_view(), name='marketplace-list'),
    path('marketplace/<int:pk>/', MarketplaceDetailView.as_view(), name='marketplace-detail'),
    path('marketplace/<int:pk>/buy/', MarketplacePurchaseView.as_view(), name='marketplace-buy'),
]
