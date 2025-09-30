# models.py

from django.db import models
from django.contrib.auth.models import User
import random, string
from ligameet.models import SportProfile
from cloudinary.models import CloudinaryField

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

    BASKETBALL_POSITIONS = [
        ('Point Guard', 'Point Guard'),
        ('Shooting Guard', 'Shooting Guard'),
        ('Small Forward', 'Small Forward'),
        ('Power Forward', 'Power Forward'),
        ('Center', 'Center'),
    ]

    VOLLEYBALL_POSITIONS = [
        ('Outside Hitter', 'Outside Hitter'),
        ('Opposite Hitter', 'Opposite Hitter'),
        ('Setter', 'Setter'),
        ('Middle Blocker', 'Middle Blocker'),
        ('Libero', 'Libero'),
        ('Defensive Specialist', 'Defensive Specialist'),
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
    image = CloudinaryField('image', folder='profile_pics', default='user_default.png')
    first_login = models.BooleanField(default=True)
    sports = models.ManyToManyField(SportProfile, blank=True)
    is_scout = models.BooleanField(default=False)

    # Sport-specific fields = Volleyball
    volleyball_position_played = models.CharField(max_length=50, blank=True, null=True)
    volleyball_jersey_number = models.IntegerField(blank=True, null=True)
    volleyball_previous_teams = models.TextField(blank=True, null=True)
    preferred_league_level = models.CharField(max_length=50, blank=True, null=True)
    
    # Sport-specific fields = Basketball
    basketball_position_played = models.CharField(max_length=50, blank=True, null=True)
    basketball_jersey_number = models.IntegerField(blank=True, null=True)
    basketball_previous_teams = models.TextField(blank=True, null=True)
    preferred_league_level = models.CharField(max_length=50, blank=True, null=True)

    # Basketball-specific fields
    basketball_playing_style = models.CharField(max_length=50, blank=True, null=True)
    vertical_leap = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    wingspan = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    basketball_achievements = models.TextField(blank=True, null=True)

    # Volleyball-specific fields
    spike_height = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    block_height = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    serving_style = models.CharField(max_length=50, blank=True, null=True)
    volleyball_achievements = models.TextField(blank=True, null=True)

    # Additional optional fields
    preferred_hand = models.CharField(max_length=15, blank=True, null=True)
    medical_info = models.TextField(blank=True, null=True)
    availability = models.CharField(max_length=100, blank=True, null=True)
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


    def generate_inv_code(self):
        """Generates a unique invitation code."""
        characters = string.ascii_letters + string.digits
        while True:
            code = ''.join(random.choice(characters) for _ in range(8))
            if not Profile.objects.filter(INV_CODE=code).exists():
                return code
    
    def get_position_choices(self):
        """Returns position choices based on the primary sport associated with the user."""
        if self.sports.exists():
            primary_sport = self.sports.first().SPORT_ID.SPORT_NAME.lower() # Get the sport name directly
            if primary_sport == 'basketball':
                return self.BASKETBALL_POSITIONS
            elif primary_sport == 'volleyball':
                return self.VOLLEYBALL_POSITIONS
        return []
    
    @classmethod
    def get_all_positions(cls):
        return cls.BASKETBALL_POSITIONS + cls.VOLLEYBALL_POSITIONS

