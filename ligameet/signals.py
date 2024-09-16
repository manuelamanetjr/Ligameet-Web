from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Wallet

@receiver(post_save, sender=User)  #creates a wallet every time a user is created
def create_wallet(sender, instance, created, **kwargs):
    if created:
        Wallet.objects.create(user=instance)


@receiver(post_save, sender=User)  #function to save the profile
def save_wallet(sender, instance, **kwargs):
    instance.wallet.save()