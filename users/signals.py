from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Profile
  
  
@receiver(post_save, sender=User)  #creates a profile every time a user is created
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)  #function to save the profile
def save_profile(sender, instance, **kwargs):
    instance.profile.save()
