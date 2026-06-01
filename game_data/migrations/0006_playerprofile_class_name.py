from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game_data', '0005_merge_20260505_1640'),
    ]

    operations = [
        migrations.AddField(
            model_name='playerprofile',
            name='class_name',
            field=models.CharField(
                choices=[
                    ('adventurer', 'Adventurer'),
                    ('mage', 'Mage'),
                    ('archer', 'Archer'),
                    ('warrior', 'Warrior'),
                ],
                default='adventurer',
                max_length=16,
            ),
        ),
    ]
