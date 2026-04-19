from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PlayerProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('level', models.PositiveIntegerField(default=1)),
                ('experience', models.PositiveIntegerField(default=0)),
                ('hp_max', models.PositiveIntegerField(default=100)),
                ('hp_current', models.PositiveIntegerField(default=100)),
                ('gold', models.PositiveIntegerField(default=0)),
                ('active_session_id', models.CharField(blank=True, default='', max_length=64)),
                ('last_sequence', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='player_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'player_profile',
                'ordering': ['user_id'],
            },
        ),
        migrations.CreateModel(
            name='PlayerSkill',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('skill_id', models.CharField(max_length=64)),
                ('name', models.CharField(max_length=120)),
                ('cooldown_seconds', models.FloatField(default=1.0)),
                ('display_order', models.PositiveIntegerField(default=0)),
                ('player_profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='skills', to='game_data.playerprofile')),
            ],
            options={
                'db_table': 'player_skill',
                'ordering': ['display_order', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='playerskill',
            constraint=models.UniqueConstraint(fields=('player_profile', 'skill_id'), name='uniq_player_skill_id'),
        ),
    ]
