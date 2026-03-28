from django.contrib.auth import authenticate, get_user_model
from django.conf import settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, RegisterSerializer

User = get_user_model()


def issue_fresh_token(user):
    Token.objects.filter(user=user).delete()
    return Token.objects.create(user=user)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token = issue_fresh_token(user)

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
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data.get('username')
        email = serializer.validated_data.get('email')
        password = serializer.validated_data['password']

        if email:
            user_obj = User.objects.filter(email__iexact=email).first()
            username = user_obj.username if user_obj else None

        user = authenticate(request=request, username=username, password=password)

        if not user:
            return Response(
                {'detail': 'Invalid credentials.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token = issue_fresh_token(user)

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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response(
            {
                'id': user.id,
                'username': user.username,
                'email': user.email,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.auth
        if token:
            token.delete()

        return Response(
            {'message': 'Logout successful.'},
            status=status.HTTP_200_OK,
        )
