from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class ExpiringTokenAuthentication(TokenAuthentication):
    """DRF TokenAuthentication with server-side expiration check."""

    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)

        ttl_seconds = int(getattr(settings, 'TOKEN_TTL_SECONDS', 3600))
        if ttl_seconds > 0:
            expires_at = token.created + timedelta(seconds=ttl_seconds)
            if timezone.now() >= expires_at:
                token.delete()
                raise AuthenticationFailed('Token has expired. Please login again.')

        return user, token
