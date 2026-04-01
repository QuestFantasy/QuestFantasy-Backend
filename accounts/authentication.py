"""
Custom authentication backend with token expiration support.

This module provides a custom token authentication class that extends
Django REST Framework's TokenAuthentication with server-side TTL enforcement.
"""
import logging
from datetime import timedelta
from typing import Tuple

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)


class ExpiringTokenAuthentication(TokenAuthentication):
    """Custom token authentication with server-side expiration check.

    Extends DRF's TokenAuthentication to enforce token TTL (time-to-live)
    based on the token creation timestamp and a configured TTL duration.

    The token is deleted if expired, forcing the user to re-authenticate.
    """

    def authenticate_credentials(self, key: str) -> Tuple[User, Token]:
        """Authenticate token and check expiration.

        Args:
            key: The authentication token key from the request

        Returns:
            Tuple of (User, Token) if authentication is successful

        Raises:
            AuthenticationFailed: If token is invalid, expired, or doesn't exist
        """
        try:
            user, token = super().authenticate_credentials(key)
        except AuthenticationFailed:
            logger.warning(
                'Invalid or non-existent token used',
                extra={'token_prefix': key[:10] if key else None},
            )
            raise

        # Check token expiration
        ttl_seconds = int(getattr(settings, 'TOKEN_TTL_SECONDS', 3600))
        if ttl_seconds > 0:
            expires_at = token.created + timedelta(seconds=ttl_seconds)
            if timezone.now() >= expires_at:
                logger.info(
                    'Expired token deleted',
                    extra={'user': user.username, 'expired_at': expires_at},
                )
                token.delete()
                raise AuthenticationFailed('Token has expired. Please login again.')

        return user, token

