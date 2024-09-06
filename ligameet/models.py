from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class Sport(models.Model):
    SPORT_NAME = models.CharField(max_length=100)
    SPORT_RULES_AND_REGULATIONS = models.TextField()
    EDITED_AT = models.DateTimeField(default=timezone.now)
    IMAGE = models.ImageField(upload_to='sports_icon/', null=True, blank=True)
    
    def __str__(self):
        return self.SPORT_NAME


class Event(models.Model):
    STATUS_CHOICES = (
        ('upcoming', 'Upcoming'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    EVENT_NAME = models.CharField(max_length=100)
    EVENT_DATE_START = models.DateTimeField()
    EVENT_DATE_END = models.DateTimeField()
    EVENT_LOCATION = models.CharField(max_length=255)
    EVENT_STATUS = models.CharField(max_length=10, choices=STATUS_CHOICES, default='upcoming')
    EVENT_ORGANIZER = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organized_events')

    def __str__(self):
        return self.EVENT_NAME


class Participant(models.Model):
    PART_TYPE_CHOICES = (
        ('player', 'Player'),
        ('coach', 'Coach'),
        ('referee', 'Referee'),
        ('spectator', 'Spectator'),
    )
    USER_ID = models.ForeignKey(User, on_delete=models.CASCADE)
    PART_TYPE = models.CharField(max_length=10, choices=PART_TYPE_CHOICES)

    def __str__(self):
        return f"{self.USER_ID.username} - {self.PART_TYPE}"


class Wallet(models.Model):
    USER_ID = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wallet')
    WALLET_BALANCE = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.USER_ID.username} - {self.WALLET_BALANCE}"


class File(models.Model):
    USER_ID = models.ForeignKey(User, on_delete=models.CASCADE)
    FILE_PATH = models.FileField(upload_to='files/')

    def __str__(self):
        return str(self.FILE_PATH)


