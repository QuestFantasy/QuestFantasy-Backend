from uuid import UUID, uuid4

from django.db import migrations, models
import django.db.models.deletion


def _reserve_instance_id(raw_value, used_ids):
    if raw_value:
        try:
            candidate = UUID(str(raw_value))
        except (TypeError, ValueError):
            candidate = uuid4()
    else:
        candidate = uuid4()

    while candidate in used_ids:
        candidate = uuid4()

    used_ids.add(candidate)
    return candidate


def forwards(apps, schema_editor):
    PlayerProfile = apps.get_model('game_data', 'PlayerProfile')
    PlayerItem = apps.get_model('game_data', 'PlayerItem')
    MarketplaceListing = apps.get_model('game_data', 'MarketplaceListing')

    db_alias = schema_editor.connection.alias
    used_ids = set()
    item_by_profile_and_id = {}

    for profile in PlayerProfile.objects.using(db_alias).all():
        for state_name, field_name in (
            ('inventory', 'inventory_items'),
            ('discarded', 'discarded_items'),
        ):
            raw_items = getattr(profile, field_name, None) or []
            for raw_item in raw_items:
                if not isinstance(raw_item, dict):
                    continue

                raw_instance_id = raw_item.get('instance_id')
                instance_id = _reserve_instance_id(raw_instance_id, used_ids)
                payload = dict(raw_item)
                payload.pop('instance_id', None)

                item = PlayerItem.objects.using(db_alias).create(
                    owner=profile,
                    instance_id=instance_id,
                    item_data=payload,
                    state=state_name,
                )
                item_by_profile_and_id[(profile.pk, str(instance_id))] = item

    for listing in MarketplaceListing.objects.using(db_alias).all():
        raw_item = listing.item_data or {}
        raw_instance_id = raw_item.get('instance_id') if isinstance(raw_item, dict) else None
        linked_item = None

        if raw_instance_id:
            linked_item = item_by_profile_and_id.get((listing.seller_id, str(raw_instance_id)))

        if linked_item is None:
            instance_id = _reserve_instance_id(raw_instance_id, used_ids)
            payload = dict(raw_item) if isinstance(raw_item, dict) else {}
            payload.pop('instance_id', None)
            linked_item = PlayerItem.objects.using(db_alias).create(
                owner=listing.seller,
                instance_id=instance_id,
                item_data=payload,
                state='listed',
            )
            item_by_profile_and_id[(listing.seller_id, str(instance_id))] = linked_item
        else:
            linked_item.owner = listing.seller
            linked_item.state = 'listed'
            linked_item.save(update_fields=['owner', 'state', 'updated_at'])

        listing.item = linked_item
        listing.save(update_fields=['item'])


class Migration(migrations.Migration):

    dependencies = [
        ('game_data', '0003_marketplacelisting'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlayerItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('instance_id', models.UUIDField(default=uuid4, editable=False, unique=True)),
                ('item_data', models.JSONField(default=dict)),
                ('state', models.CharField(choices=[('inventory', 'Inventory'), ('discarded', 'Discarded'), ('listed', 'Listed')], db_index=True, default='inventory', max_length=16)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='game_data.playerprofile')),
            ],
            options={
                'db_table': 'player_item',
                'ordering': ['id'],
            },
        ),
        migrations.AddField(
            model_name='marketplacelisting',
            name='item',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='marketplace_listings', to='game_data.playeritem'),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='playerprofile',
            name='inventory_items',
        ),
        migrations.RemoveField(
            model_name='playerprofile',
            name='discarded_items',
        ),
        migrations.RemoveField(
            model_name='marketplacelisting',
            name='item_data',
        ),
        migrations.AlterField(
            model_name='marketplacelisting',
            name='item',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='marketplace_listings', to='game_data.playeritem'),
        ),
    ]