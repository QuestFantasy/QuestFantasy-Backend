"""
Custom exception handlers for API error responses.

This module provides centralized exception handling to ensure
consistent error response formatting across the API.
"""
import logging
from typing import Tuple, Dict, Any

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def custom_exception_handler(exc: Exception, context: Dict[str, Any]) -> Response:
    """Handle API exceptions with custom response format.

    Args:
        exc: The exception that was raised
        context: Context information about the request

    Returns:
        Response with custom error format or None if exception is not handled
    """
    # Call REST Framework's default exception handler first
    response = exception_handler(exc, context)

    if response is not None:
        # Log authentication and authorization failures for security audit
        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            logger.warning(
                "Authentication failed",
                extra={
                    'user': context.get('request').user if context.get('request') else None,
                    'path': context.get('request').path if context.get('request') else None,
                },
            )
        elif response.status_code == status.HTTP_403_FORBIDDEN:
            logger.warning(
                "Authorization denied",
                extra={
                    'user': context.get('request').user if context.get('request') else None,
                    'path': context.get('request').path if context.get('request') else None,
                },
            )
        elif response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            logger.warning("Rate limit exceeded", extra={'path': context.get('request').path})

        # Customize response format
        if 'detail' not in response.data:
            response.data = {
                'error': response.data,
                'status_code': response.status_code,
            }
    else:
        # Handle unexpected server errors
        logger.error(
            'Unhandled exception',
            exc_info=True,
            extra={'path': context.get('request').path if context.get('request') else None},
        )
        response = Response(
            {
                'error': 'An unexpected error occurred',
                'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response
