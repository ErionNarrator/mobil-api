from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView
)

from .views import (
    RegisterView,
    UserProfileView,
    UserAccountViewSet,
    CurrencyViewSet,
    TransactionViewSet,
    TransferView
)

# Create a router for ViewSets
router = DefaultRouter()
router.register(r'accounts', UserAccountViewSet)
router.register(r'currencies', CurrencyViewSet)
router.register(r'transactions', TransactionViewSet)

urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    
    # Authentication endpoints
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # User profile
    path('profile/', UserProfileView.as_view(), name='user_profile'),
    
    # Transfer endpoint
    path('transfer/', TransferView.as_view(), name='transfer'),
    
    # DRF auth
    path('auth/', include('rest_framework.urls', namespace='rest_framework')),
]
