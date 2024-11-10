from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from ligameet.models import SportProfile, Sport

class Command(BaseCommand):
    help = 'Verify players associated with a sport'

    def handle(self, *args, **kwargs):
        sport_id = 1  # Assuming Basketball
        basketball = Sport.objects.get(id=sport_id)

        available_players = User.objects.filter(
            profile__role='Player',
            profile__sports__id=sport_id
        )
        self.stdout.write(f"Available players for sport_id {sport_id}: {available_players.values_list('id', 'username')}")

        for player in available_players:
            self.stdout.write(f"Player: {player.username}, Sports: {player.profile.sports.all()}")
