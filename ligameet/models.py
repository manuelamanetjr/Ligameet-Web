from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from PIL import Image

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
        ('finished', 'finished'),  # Replaced 'completed'
        ('cancelled', 'Cancelled'),
    )
    EVENT_NAME = models.CharField(max_length=100)
    EVENT_DATE_START = models.DateTimeField()
    EVENT_DATE_END = models.DateTimeField() 
    EVENT_LOCATION = models.CharField(max_length=255)
    EVENT_STATUS = models.CharField(max_length=10, choices=STATUS_CHOICES, default='upcoming')
    EVENT_ORGANIZER = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organized_events')
    EVENT_IMAGE = models.ImageField(upload_to='event_images/', null=True, blank=True) 
    SPORT_ID = models.ForeignKey(Sport, on_delete=models.CASCADE, related_name='events')

    def __str__(self):
        return self.EVENT_NAME
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.EVENT_IMAGE:  # Check if an image is associated
            img = Image.open(self.EVENT_IMAGE.path)

            if img.height > 300 or img.width > 300:
                output_size = (300, 300)
                img.thumbnail(output_size)
                img.save(self.EVENT_IMAGE.path)

    def update_status(self):
        now = timezone.now()
        if self.EVENT_DATE_END < now:
            self.EVENT_STATUS = 'finished'
        elif self.EVENT_DATE_START <= now <= self.EVENT_DATE_END:
            self.EVENT_STATUS = 'ongoing'
        else:
            self.EVENT_STATUS = 'upcoming'
        self.save()

class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    WALLET_BALANCE = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.user} - {self.WALLET_BALANCE}"

class SportProfile(models.Model):  #TODO make a view to edit the sports he played
    USER_ID = models.ForeignKey(User, on_delete=models.CASCADE)
    SPORT_ID = models.ForeignKey(Sport, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['USER_ID', 'SPORT_ID'], name='unique_user_sport')
        ]

    def __str__(self):
        return f"{self.USER_ID.username} participating in {self.SPORT_ID.SPORT_NAME}"


class File(models.Model):
    USER_ID = models.ForeignKey(User, on_delete=models.CASCADE)
    FILE_PATH = models.FileField(upload_to='files/')

    def __str__(self):
        return str(self.FILE_PATH)


class Team(models.Model):
    TEAM_NAME = models.CharField(max_length=100)
    TEAM_TYPE = models.CharField(max_length=50) #junior senior
    SPORT_ID = models.ForeignKey(Sport, on_delete=models.CASCADE)   
    COACH_ID = models.ForeignKey(User, on_delete=models.CASCADE)
    
    def __str__(self):
        return self.TEAM_NAME

class TeamParticipant(models.Model):
    IS_CAPTAIN = models.BooleanField(default=False)
    USER_ID = models.ForeignKey(User, on_delete=models.CASCADE) #PART_ID
    TEAM_ID = models.ForeignKey(Team, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['USER_ID', 'TEAM_ID'], name='unique_team_user') # unique_team_participant
        ]

    def __str__(self):
        return f"{self.USER_ID} - {self.TEAM_ID}"


class TeamEvent(models.Model):
    TEAM_ID = models.ForeignKey(Team, on_delete=models.CASCADE)
    EVENT_ID = models.ForeignKey(Event, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['TEAM_ID', 'EVENT_ID'], name='unique_team_event')
        ]

    def __str__(self):
        return f"Team: {self.TEAM_ID.TEAM_NAME} - Event: {self.EVENT_ID.EVENT_NAME}"
    

class Match(models.Model):
    MATCH_TYPE = models.CharField(max_length=50) #casual official
    MATCH_CATEGORY = models.CharField(max_length=50) #CIVIRAA
    MATCH_SCORE = models.IntegerField(default=0)
    MATCH_DATE = models.DateTimeField()
    MATCH_STATUS = models.CharField(max_length=20)
    TEAM_ID = models.ForeignKey(Team, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.MATCH_TYPE} - {self.TEAM_ID.TEAM_NAME} on {self.MATCH_DATE}"


class Subscription(models.Model):
    SUB_PLAN = models.CharField(max_length=50)
    SUB_DATE_STARTED = models.DateTimeField(default=timezone.now)
    SUB_DATE_END = models.DateTimeField()
    USER_ID = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.USER_ID.username} - {self.SUB_PLAN} (Started: {self.SUB_DATE_STARTED})"
    

class TeamRegistrationFee(models.Model):
    TEAM_ID = models.ForeignKey(Team, on_delete=models.CASCADE)
    MATCH_ID = models.ForeignKey(Match, on_delete=models.CASCADE)
    REGISTRATION_FEE = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    IS_PAID = models.BooleanField(default=False)

    def __str__(self):
        return f"Team: {self.TEAM_ID.TEAM_NAME} - Match: {self.MATCH_ID.MATCH_TYPE} - Paid: {self.IS_PAID}"
    

class SportsEvent(models.Model):
    EVENT_ID = models.OneToOneField(Event, on_delete=models.CASCADE, primary_key=True)
    SPORTS_ID = models.ForeignKey(Sport, on_delete=models.CASCADE)

    def __str__(self):
        return f"Event: {self.EVENT_ID.EVENT_NAME} - Sport: {self.SPORTS_ID.SPORT_NAME}"


class TeamMatch(models.Model):
    TEAM_ID = models.ForeignKey(Team, on_delete=models.CASCADE)
    MATCH_ID = models.ForeignKey(Match, on_delete=models.CASCADE)
    IS_WINNER = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['TEAM_ID', 'MATCH_ID'], name='unique_team_match')
        ]

    def __str__(self):
        return f"Team: {self.TEAM_ID.TEAM_NAME} - Match: {self.MATCH_ID.MATCH_TYPE} - Winner: {self.IS_WINNER}"


class UserMatch(models.Model):
    MATCH_ID = models.ForeignKey(Match, on_delete=models.CASCADE)
    USER_ID = models.ForeignKey(User, on_delete=models.CASCADE)
    TEAM_ID = models.ForeignKey(Team, on_delete=models.CASCADE)
    IS_WINNER = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['MATCH_ID', 'USER_ID'], name='unique_user_match')
        ]

    def __str__(self):
        return f"Match: {self.MATCH_ID.MATCH_TYPE} - User: {self.USER_ID.username} - Team: {self.TEAM_ID.TEAM_NAME} - Winner: {self.IS_WINNER}"


class VolleyballStats(models.Model):
    VB_STATS_PT_COUNT = models.IntegerField(default=0)
    VB_STATS_ASSIST = models.IntegerField(default=0)
    VB_STATS_BLOCK = models.IntegerField(default=0)
    VB_STATS_ERROR = models.IntegerField(default=0)
    VB_STATS_IS_MVP = models.BooleanField(default=False)
    VB_STATS_SET = models.IntegerField(default=0)
    USER_ID = models.ForeignKey(User, on_delete=models.CASCADE)
    MATCH_ID = models.ForeignKey(Match, on_delete=models.CASCADE)
    USER_MATCH_ID = models.ForeignKey(UserMatch, on_delete=models.CASCADE)

    def __str__(self):
        return f"User: {self.USER_ID.username} - Match: {self.MATCH_ID.MATCH_TYPE} - MVP: {self.VB_STATS_IS_MVP}"


class UserRegistrationFee(models.Model):
    USER_MATCH_ID = models.ForeignKey(UserMatch, on_delete=models.CASCADE)
    IS_PAID = models.BooleanField(default=False)

    def __str__(self):
        return f"UserMatch: {self.USER_MATCH_ID} - Paid: {self.IS_PAID}"


class Payment(models.Model):
    PAYMENT_AMOUNT = models.DecimalField(max_digits=10, decimal_places=2)
    PAYMENT_DATE = models.DateTimeField(default=timezone.now)
    WALLET_ID = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    SUBSCRIPTION_ID = models.ForeignKey(Subscription, on_delete=models.CASCADE, null=True, blank=True)
    TEAM_REGISTRATION_ID = models.ForeignKey(TeamRegistrationFee, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"Amount: {self.PAYMENT_AMOUNT} - Date: {self.PAYMENT_DATE}"


class Transaction(models.Model):
    TRANSACTION_DATE = models.DateTimeField(default=timezone.now)
    TRANSACTION_AMOUNT = models.DecimalField(max_digits=10, decimal_places=2)
    PAYMENT_ID = models.ForeignKey(Payment, on_delete=models.CASCADE)
    USER_ID = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"Transaction Date: {self.TRANSACTION_DATE} - Amount: {self.TRANSACTION_AMOUNT} - User: {self.USER_ID.username}"
    
class JoinRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    USER_ID = models.ForeignKey(User, on_delete=models.CASCADE)
    TEAM_ID = models.ForeignKey(Team, on_delete=models.CASCADE)
    STATUS = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    REQUEST_DATE = models.DateTimeField(default=timezone.now)
        
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['USER_ID', 'TEAM_ID'], name='unique_join_request')
        ]

    def __str__(self):
        return f"{self.USER_ID.username} requesting to join {self.TEAM_ID.TEAM_NAME} - Status: {self.STATUS}"
    
class Activity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Reference to the user
    description = models.TextField()  # Description of the activity
    timestamp = models.DateTimeField(auto_now_add=True)  # Automatically set to the time of creation

    def __str__(self):
        return f"{self.user.username} - {self.description} on {self.timestamp}"

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f'Notification for {self.user.username}: {self.message}'