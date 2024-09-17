# models.py

from django.db import models
from django.contrib.auth.models import User
from PIL import Image

class Profile(models.Model):
    ROLE_CHOICES = [
        ('Player', 'Player'),
        ('Coach', 'Coach'),
        ('Scout', 'Scout'),
        ('Event Organizer', 'Event Organizer'),
    ]

    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    FIRST_NAME = models.CharField(max_length=30, default='')
    LAST_NAME = models.CharField(max_length=30, default='')
    MIDDLE_NAME = models.CharField(max_length=30, blank=True, null=True)
    DATE_OF_BIRTH = models.DateField(blank=True, null=True)
    GENDER = models.CharField(max_length=1, choices=GENDER_CHOICES, default='-')
    ADDRESS = models.CharField(max_length=255, blank=True, null=True)
    HEIGHT = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    WEIGHT = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    PHONE = models.CharField(max_length=15, blank=True, null=True)
    INV_CODE = models.CharField(max_length=50, blank=True, null=True)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, blank=True, null=True)
    image = models.ImageField(default='user_default.png', upload_to='profile_pics')

    def __str__(self):
        return f'{self.user.username} Profile'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        img = Image.open(self.image.path)

        if img.height > 300 or img.width > 300:
            output_size = (300, 300)
            img.thumbnail(output_size)
            img.save(self.image.path)
