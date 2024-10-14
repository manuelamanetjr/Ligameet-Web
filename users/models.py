# models.py

from django.db import models
from django.contrib.auth.models import User
from PIL import Image
import random, string

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
    INV_CODE = models.CharField(max_length=50, blank=True, null=True, unique=True)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, blank=True, null=True)
    image = models.ImageField(default='user_default.png', upload_to='profile_pics')
    first_login = models.BooleanField(default=True)

    
   # Sport-specific fields
    position_played = models.CharField(max_length=50, blank=True, null=True)  # For both sports (e.g., Point Guard, Shooting Guard, Small Forward, Power Forward, Center)
    jersey_number = models.IntegerField(blank=True, null=True) #(for team registration)
    preferred_hand = models.CharField(max_length=15, blank=True, null=True)  # Common for both sports
    previous_teams = models.TextField(blank=True, null=True)
    preferred_league_level = models.CharField(max_length=50, blank=True, null=True)  # e.g., Amateur, Semi-pro

    # Basketball-specific fields
    basketball_playing_style = models.CharField(max_length=50, blank=True, null=True) #(e.g., Defensive, Offensive, All-rounder)
    vertical_leap = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True) # (In inches or cm, used for positions like Center or Power Forward)
    wingspan = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True) # (Important for blocking and defending)
    basketball_achievements = models.TextField(blank=True, null=True)

    # Volleyball-specific fields
    spike_height = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True) #(Height of the player’s highest spike)
    block_height = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    serving_style = models.CharField(max_length=50, blank=True, null=True) #(e.g., Jump Serve, Float Serve, Underhand Serve)
    volleyball_achievements = models.TextField(blank=True, null=True)

    # Additional optional fields
    medical_info = models.TextField(blank=True, null=True)  # Relevant medical history or limitations
    availability = models.CharField(max_length=100, blank=True, null=True)  # Availability for matches/practices
    preferred_coaches = models.TextField(blank=True, null=True)


    def __str__(self):
        return f'{self.user.username} Profile'
    
    def full_name(self):
        return f"{self.FIRST_NAME} {self.LAST_NAME}"
    
    def save(self, *args, **kwargs):
        # Generate unique invitation code if not set
        if not self.INV_CODE:
            self.INV_CODE = self.generate_inv_code()
        
        super().save(*args, **kwargs)

        img = Image.open(self.image.path)

        if img.height > 300 or img.width > 300:
            output_size = (300, 300)
            img.thumbnail(output_size)
            img.save(self.image.path)

    def generate_inv_code(self):
        """Generates a unique invitation code."""
        characters = string.ascii_letters + string.digits
        while True:
            code = ''.join(random.choice(characters) for _ in range(8))
            if not Profile.objects.filter(INV_CODE=code).exists():
                return code