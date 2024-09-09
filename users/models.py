from django.db import models
from django.contrib.auth.models import User
from PIL import Image


class Profile(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]

    TYPE_CHOICES = [
        ('COACH', 'Coach'),
        ('ATHLETE', 'Athlete'),
        ('SCOUT', 'Scout'),
        ('EVENT_ORG', 'Event Organizer'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=30, default='')
    last_name = models.CharField(max_length=30, default='')
    middle_name = models.CharField(max_length=30, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='')
    address = models.CharField(max_length=255, blank=True, null=True)
    height = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)  # For storing height in meters
    weight = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)  # For storing weight in kilograms
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    type = models.CharField(max_length=15, choices=TYPE_CHOICES, blank=True, null=True)
    inv_code = models.CharField(max_length=50, blank=True, null=True)
    is_coach = models.BooleanField(default=False)
    is_athlete = models.BooleanField(default=False)
    is_scout = models.BooleanField(default=False)
    is_event_org = models.BooleanField(default=False)
    image = models.ImageField(default='user_default.png', upload_to='profile_pics')

    def __str__(self):
        return f'{self.user.username} Profile'  # On the admin page

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        img = Image.open(self.image.path)

        if img.height > 300 or img.width > 300:
            output_size = (300, 300)
            img.thumbnail(output_size)
            img.save(self.image.path)
