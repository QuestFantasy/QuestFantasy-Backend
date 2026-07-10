from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import MarketplaceListing, PlayerItem, PlayerProfile


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
        profile = PlayerProfile.objects.get(user=self.user)
        self.assertEqual(profile.gold, 100)

    def test_unauthorized_profile_request_is_rejected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_profile_success(self):
        self.authenticate()
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['level'], 1)
        self.assertEqual(response.data['gold'], 100)
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

    def test_patch_profile_rejects_excessive_gold(self):
        self.authenticate()
        response = self.client.patch(
            self.url,
            {'gold': 999999},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['ignored'])
        self.assertEqual(response.data['reason'], 'invalid_gold_gain')

    def test_patch_profile_rejects_excessive_hp_max(self):
        self.authenticate()
        response = self.client.patch(
            self.url,
            {'hp_max': 99999},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['ignored'])
        self.assertEqual(response.data['reason'], 'invalid_hp_max')

    def test_patch_profile_rejects_level_jump(self):
        self.authenticate()
        response = self.client.patch(
            self.url,
            {'level': 10},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['ignored'])
        self.assertEqual(response.data['reason'], 'invalid_level_jump')

    def test_patch_profile_rejects_hacked_item_spawn(self):
        self.authenticate()
        # Spawn an equipment with 9999 ATK
        response = self.client.patch(
            self.url,
            {
                'inventory_items': [
                    {
                        'instance_id': '99999999-9999-9999-9999-999999999999',
                        'name': 'God Sword',
                        'item_type': 'weapon',
                        'rarity': 5,
                        'level_requirement': 1,
                        'abilities': {
                            'atk': 9999,
                            'def': 0,
                            'spd': 0,
                            'vit': 0
                        }
                    }
                ]
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['ignored'])
        self.assertIn('item_validation_failed', response.data['reason'])

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

    def test_patch_profile_persists_items_in_player_item_table(self):
        self.authenticate()
        response = self.client.patch(
            self.url,
            {
                'inventory_items': [
                    {'name': 'Iron Sword', 'attack': 12},
                ],
                'discarded_items': [
                    {'instance_id': '11111111-1111-1111-1111-111111111111', 'name': 'Old Shield'},
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['inventory_items']), 1)
        self.assertEqual(len(response.data['discarded_items']), 1)
        self.assertEqual(PlayerItem.objects.filter(owner=self.user.player_profile).count(), 2)

    def test_marketplace_purchase_transfers_item_ownership(self):
        self.authenticate()
        create_response = self.client.patch(
            self.url,
            {
                'inventory_items': [
                    {'instance_id': '22222222-2222-2222-2222-222222222222', 'name': 'Silver Ring'},
                ],
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_200_OK)

        listing_response = self.client.post(
            reverse('marketplace-list'),
            {
                'item_data': create_response.data['inventory_items'][0],
                'price': 25,
            },
            format='json',
        )
        self.assertEqual(listing_response.status_code, status.HTTP_201_CREATED)

        buyer = User.objects.create_user(
            username='buyer1',
            email='buyer1@example.com',
            password='StrongPass123!',
        )
        buyer_token = Token.objects.create(user=buyer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {buyer_token.key}')

        buy_response = self.client.post(
            reverse('marketplace-buy', args=[listing_response.data['id']]),
            {},
            format='json',
        )

        self.assertEqual(buy_response.status_code, status.HTTP_200_OK)

        listing = MarketplaceListing.objects.get(pk=listing_response.data['id'])
        item = listing.item
        self.assertEqual(listing.status, MarketplaceListing.Status.SOLD)
        self.assertEqual(item.owner, buyer.player_profile)
        self.assertEqual(item.state, PlayerItem.State.INVENTORY)
        self.assertEqual(str(item.instance_id), '22222222-2222-2222-2222-222222222222')
