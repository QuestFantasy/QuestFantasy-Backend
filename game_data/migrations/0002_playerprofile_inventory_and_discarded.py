from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("game_data", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="playerprofile",
            name="inventory_items",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="playerprofile",
            name="discarded_items",
            field=models.JSONField(blank=True, default=list),
        ),
    ]

