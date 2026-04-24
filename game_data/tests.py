from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import PlayerProfile


User = get_user_model()


class PlayerProfileApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='player1',
            email='player1@example.com',
            password='StrongPass123!',
        )
        self.token = Token.objects.create(user=self.user)
        self.url = reverse('player-profile')

    def authenticate(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

    def test_profile_auto_created_on_user_create(self):
        self.assertTrue(PlayerProfile.objects.filter(user=self.user).exists())

    def test_unauthorized_profile_request_is_rejected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_profile_success(self):
        self.authenticate()
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['level'], 1)
        self.assertIn('skills', response.data)
        self.assertEqual(len(response.data['skills']), 3)

    def test_patch_profile_validates_hp_bounds(self):
        self.authenticate()
        response = self.client.patch(
            self.url,
            {'hp_max': 100, 'hp_current': 101},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_profile_with_sequence_is_idempotent(self):
        self.authenticate()
        payload = {
            'session_id': 'session-a',
            'sequence': 1,
            'experience': 10,
        }
        first = self.client.patch(self.url, payload, format='json')
        second = self.client.patch(self.url, payload, format='json')

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertFalse(first.data['ignored'])
        self.assertTrue(second.data['ignored'])

    def test_patch_profile_replaces_skills_list(self):
        self.authenticate()
        response = self.client.patch(
            self.url,
            {
                'skills': [
                    {
                        'skill_id': 'basic_attack',
                        'name': 'Sword Attack',
                        'cooldown_seconds': 0.3,
                        'display_order': 0,
                    },
                    {
                        'skill_id': 'bow_attack',
                        'name': 'Bow Attack',
                        'cooldown_seconds': 0.6,
                        'display_order': 1,
                    },
                    {
                        'skill_id': 'fireball',
                        'name': 'Fireball',
                        'cooldown_seconds': 1.5,
                        'display_order': 2,
                    },
                    {
                        'skill_id': 'power_shot',
                        'name': 'Power Shot',
                        'cooldown_seconds': 2.0,
                        'display_order': 3,
                    },
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['skills']), 4)
