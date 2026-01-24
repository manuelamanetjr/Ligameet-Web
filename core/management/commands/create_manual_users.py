# core/management/commands/create_manual_users.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

USERS = [
    {"username": "test.user", "email": "test.user@gmail.com", "password": "P4$$w0RD"},
    {"username": "user.test", "email": "user.test@gmail.com", "password": "P4$$w0RD"},
]


class Command(BaseCommand):
    help = "Create users matching the register form"

    def handle(self, *args, **options):
        for data in USERS:
            user, created = User.objects.get_or_create(
                username=data["username"],
                defaults={"email": data["email"]},
            )

            if created:
                user.set_password(data["password"])
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Created {user.username}"))
            else:
                self.stdout.write(f"Skipped {user.username} (already exists)")

