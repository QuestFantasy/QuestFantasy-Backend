"""
Health check endpoints for monitoring application status.

This module provides health check endpoints that can be used by
load balancers, orchestration platforms, and monitoring systems
to verify the application is running and healthy.
"""
import logging
from typing import Dict, Any

from django.db import connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class HealthCheckView(APIView):
    """Basic health check endpoint.

    GET /api/health/ - Returns HTTP 200 if service is running

    Attributes:
        permission_classes: Allow unauthenticated access
    """

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        """Check if the API service is running.

        Args:
            request: HTTP request

        Returns:
            Response with service status

        Status Codes:
            200: Service is healthy and running
        """
        return Response(
            {
                'status': 'healthy',
                'service': 'QuestFantasy API',
            },
            status=status.HTTP_200_OK,
        )


class DatabaseHealthCheckView(APIView):
    """Database connectivity health check.

    GET /api/health/db/ - Verifies database connection

    Attributes:
        permission_classes: Allow unauthenticated access
    """

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        """Check database connectivity.

        Args:
            request: HTTP request

        Returns:
            Response with database connection status

        Status Codes:
            200: Database connection successful
            503: Database connection failed
        """
        try:
            # Try to execute a simple query on the database
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()

            return Response(
                {
                    'status': 'healthy',
                    'service': 'QuestFantasy API',
                    'database': 'connected',
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error('Database health check failed', exc_info=True)
            return Response(
                {
                    'status': 'unhealthy',
                    'service': 'QuestFantasy API',
                    'database': 'disconnected',
                    'error': str(e),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class ReadinessCheckView(APIView):
    """Readiness probe for orchestration platforms.

    GET /api/health/ready/ - Verifies service is ready to accept requests

    Attributes:
        permission_classes: Allow unauthenticated access
    """

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        """Check if service is ready to accept requests.

        Includes database connectivity check.

        Args:
            request: HTTP request

        Returns:
            Response with readiness status

        Status Codes:
            200: Service is ready
            503: Service is not ready
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()

            return Response(
                {
                    'ready': True,
                    'service': 'QuestFantasy API',
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error('Readiness check failed', exc_info=True)
            return Response(
                {
                    'ready': False,
                    'service': 'QuestFantasy API',
                    'error': str(e),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
