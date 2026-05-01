from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game_data', '0002_playerprofile_inventory_and_discarded'),
    ]

    operations = [
        migrations.AddField(
            model_name='playerprofile',
            name='equipped_items',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
