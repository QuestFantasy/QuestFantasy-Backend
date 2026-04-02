"""
Views for user authentication and account management.

This module provides REST API endpoints for user registration, login,
logout, and profile management with proper security controls.
"""
import logging
from typing import Type

from django.contrib.auth import authenticate, get_user_model
from django.conf import settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, RegisterSerializer, UserDetailSerializer

User = get_user_model()
logger = logging.getLogger(__name__)


def issue_fresh_token(user: User) -> Token:
    """Issue a fresh authentication token for a user.

    Deletes any existing tokens and creates a new one.

    Args:
        user: User instance to issue token for

    Returns:
        Newly created Token instance
    """
    Token.objects.filter(user=user).delete()
    return Token.objects.create(user=user)


class RegisterView(APIView):
    """Handle user registration.

    POST /api/auth/register/ - Register a new user account

    Attributes:
        permission_classes: Allow unauthenticated access
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        """Register a new user account.

        Args:
            request: HTTP request containing username, email, password, confirm_password

        Returns:
            Response with success message, auth token, and user details

        Status Codes:
            201: User successfully created
            400: Validation error (invalid data or user already exists)
        """
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token = issue_fresh_token(user)

        logger.info(
            'User registered successfully',
            extra={'username': user.username, 'email': user.email},
        )

        return Response(
            {
                'message': 'Registration successful.',
                'token': token.key,
                'token_ttl_seconds': settings.TOKEN_TTL_SECONDS,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """Handle user login.

    POST /api/auth/login/ - Authenticate user and issue token

    Attributes:
        permission_classes: Allow unauthenticated access
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        """Authenticate user and issue authentication token.

        Args:
            request: HTTP request containing username/email and password

        Returns:
            Response with success message, auth token, and user details

        Status Codes:
            200: User successfully authenticated
            400: Validation error (missing required fields)
            401: Invalid credentials
        """
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data.get('username')
        email = serializer.validated_data.get('email')
        password = serializer.validated_data['password']

        # Convert email to username if email login is used
        if email:
            user_obj = User.objects.filter(email__iexact=email).first()
            if user_obj:
                username = user_obj.username
            else:
                logger.warning(
                    'Login attempt with non-existent email',
                    extra={'email': email},
                )

        # Authenticate with username
        user = authenticate(request=request, username=username, password=password)

        if not user:
            logger.warning(
                'Failed login attempt',
                extra={'username': username},
            )
            return Response(
                {'detail': 'Invalid credentials.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token = issue_fresh_token(user)

        logger.info(
            'User logged in successfully',
            extra={'username': user.username},
        )

        return Response(
            {
                'message': 'Login successful.',
                'token': token.key,
                'token_ttl_seconds': settings.TOKEN_TTL_SECONDS,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                },
            },
            status=status.HTTP_200_OK,
        )


class ProfileView(APIView):
    """Retrieve authenticated user's profile information.

    GET /api/auth/me/ - Get current user details

    Attributes:
        permission_classes: Require authentication
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        """Get current authenticated user's profile.

        Returns only safe, non-sensitive user information.

        Args:
            request: HTTP request with authentication token

        Returns:
            Response with user profile details (limited fields)

        Status Codes:
            200: Profile retrieved successfully
            401: Authentication required
        """
        serializer = UserDetailSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """Handle user logout.

    POST /api/auth/logout/ - Invalidate authentication token

    Attributes:
        permission_classes: Require authentication
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        """Logout user by invalidating their authentication token.

        Args:
            request: HTTP request with authentication token

        Returns:
            Response with success message

        Status Codes:
            200: Logout successful
            401: Authentication required
        """
        token = request.auth
        if token:
            logger.info(
                'User logged out',
                extra={'username': request.user.username},
            )
            token.delete()
        else:
            logger.warning(
                'Logout attempt without valid token',
                extra={'user_id': request.user.id},
            )

        return Response(
            {'message': 'Logout successful.'},
            status=status.HTTP_200_OK,
        )

