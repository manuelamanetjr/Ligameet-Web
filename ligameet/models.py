from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from PIL import Image
from django.core.validators import MinValueValidator 
from django.db.models import Q
from datetime import date
from django.db.models import Sum
from cloudinary.models import CloudinaryField


class Sport(models.Model):
    SPORT_NAME = models.CharField(max_length=100)
    SPORT_RULES_AND_REGULATIONS = models.TextField()
    EDITED_AT = models.DateTimeField(default=timezone.now)
    IMAGE = CloudinaryField('image', folder='sport_images', blank=True, null=True)
    
    def __str__(self):
        return self.SPORT_NAME
    
    def get_recent_matches(self, limit=5):
        from .models import MatchDetails  # Import here to avoid circular import
        
        # Get matches for this sport
        matches = MatchDetails.objects.filter(
            Q(team1__SPORT_ID=self) & Q(team2__SPORT_ID=self)
        ).select_related('team1', 'team2', 'match')
        
        # Order by most recent and limit results
        recent_matches = matches.order_by('-match__MATCH_DATE')[:limit]
        
        return recent_matches
    
class Team(models.Model):
    TEAM_NAME = models.CharField(max_length=100)
    TEAM_TYPE = models.CharField(max_length=50) #junior senior, midget
    SPORT_ID = models.ForeignKey(Sport, on_delete=models.CASCADE)   
    COACH_ID = models.ForeignKey(User, on_delete=models.CASCADE)
    TEAM_LOGO = CloudinaryField('image', folder='team_logos', blank=True, null=True)
    TEAM_DESCRIPTION = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.TEAM_NAME
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.TEAM_LOGO:  # Check if an image is associated   
            img = Image.open(self.TEAM_LOGO.path)
            try:
                if img.height > 300 or img.width > 300:
                    output_size = (300, 300)
                    img.thumbnail(output_size)
                    img.save(self.TEAM_LOGO.path)
            except Exception as e:
                print(f"Error processing image: {e}")



class Event(models.Model):
    STATUS_CHOICES = (
        ('Draft', 'Draft'),
        ('open', 'Open For Registration'),
        ('ongoing', 'Ongoing'),
        ('finished', 'Finished'),  
        ('cancelled', 'Cancelled'), #TODO cancel event
    )
    EVENT_NAME = models.CharField(max_length=100)
    EVENT_DATE_START = models.DateTimeField()
    EVENT_DATE_END = models.DateTimeField() 
    EVENT_LOCATION = models.CharField(max_length=255)
    EVENT_STATUS = models.CharField(max_length=21, choices=STATUS_CHOICES, default='Draft')
    EVENT_ORGANIZER = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organized_events')
    EVENT_IMAGE = CloudinaryField('image', folder='event_images', blank=True, null=True)
    SPORT = models.ManyToManyField(Sport, related_name='events')  
    PAYMENT_FEE = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    IS_SPONSORED = models.BooleanField(default=False)
    IS_POSTED = models.BooleanField(default=False)  #TODO backend
    CONTACT_PERSON = models.CharField(max_length=100, null=True, blank=True) 
    CONTACT_PHONE = models.CharField(max_length=15, null=True, blank=True)
    REGISTRATION_DEADLINE = models.DateTimeField(null=True, blank=True) #TODO remove NULL/BLANK
    teams = models.ManyToManyField(Team, through='TeamEvent', related_name='events')

    def __str__(self):
        sports_names = ', '.join(sport.SPORT_NAME for sport in self.SPORT.all())
        return f"{self.EVENT_NAME} - {sports_names}"
        

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.EVENT_IMAGE:  # Check if an image is associated
            img = Image.open(self.EVENT_IMAGE.path)

            if img.height > 300 or img.width > 300:
                output_size = (300, 300)
                img.thumbnail(output_size)
                img.save(self.EVENT_IMAGE.path)



    def transfer_money_to_organizer(self):
        """Transfers 80% of the total registration fees collected (based on SportDetails.entrance_fee) to the organizer's wallet."""
        if self.EVENT_STATUS == 'finished':
            print(f"Transfer method triggered for event: {self.EVENT_NAME}")

            # Initialize total collected fees
            total_collected_fees = Decimal('0.0')

            # Iterate through all team categories linked to the event
            for team_category in self.team_categories.all():
                # Access the SportDetails for the team category
                sport_details = team_category.sport_details.first()

                if sport_details:
                    # Calculate the total collected fees for this team category
                    entrance_fee = sport_details.entrance_fee
                    teams_registered = sport_details.teams.count()  # Number of teams registered for this sport
                    total_collected_fees += entrance_fee * Decimal(teams_registered)

                    print(
                        f"Team Category: {team_category.name}, Sport: {team_category.sport.SPORT_NAME}, "
                        f"Entrance Fee: {entrance_fee}, Teams Registered: {teams_registered}"
                    )

            if total_collected_fees <= 0:
                print(f"No money to transfer for event: {self.EVENT_NAME}")
                return

            # Calculate 80% of the total collected fees
            amount_to_transfer = total_collected_fees * Decimal('0.8')
            print(f"Amount to Transfer: {amount_to_transfer}")

            try:
                # Access the wallet of the event organizer
                organizer_wallet = Wallet.objects.get(user=self.EVENT_ORGANIZER)
                print(f"Current Wallet Balance: {organizer_wallet.WALLET_BALANCE}")

                # Update the wallet balance
                organizer_wallet.WALLET_BALANCE += amount_to_transfer
                organizer_wallet.save()

                print(f"New Wallet Balance: {organizer_wallet.WALLET_BALANCE}")
            except Wallet.DoesNotExist:
                print(f"Error: Wallet for {self.EVENT_ORGANIZER.username} does not exist.")



    def update_status(self):
        now = timezone.now()
        today = now.date()
        print(f"Current DateTime: {now}, Event Start: {self.EVENT_DATE_START}, Event End: {self.EVENT_DATE_END}, Registration Deadline: {self.REGISTRATION_DEADLINE}, Status: {self.EVENT_STATUS}")

        # Ensure self.EVENT_DATE_START is timezone-aware
        if timezone.is_naive(self.EVENT_DATE_START):
            self.EVENT_DATE_START = timezone.make_aware(self.EVENT_DATE_START, timezone.get_current_timezone())

        event_start_local = timezone.localtime(self.EVENT_DATE_START)
        

        # Do nothing if the event status is 'Draft' or 'cancelled'
        if self.EVENT_STATUS in ['draft', 'cancelled']:
            
            return

        # If the event has ended
        if self.EVENT_DATE_END < now:
            if self.EVENT_STATUS != 'finished':
                self.EVENT_STATUS = 'finished'
                self.save()  # Save status change
                self.transfer_money_to_organizer()  # Transfer money only when status changes
                print(f"Event has ended. Updating status to 'finished' and transferring money.")
            return

        # Check if all sports in the event meet the required number of teams
        all_sports_ready = True
        for sport_detail in SportDetails.objects.filter(team_category__event=self):
            teams_registered = sport_detail.teams.count()
            
            if teams_registered < sport_detail.number_of_teams:
                all_sports_ready = False
                
                break

        # New conditions for registration deadline and status
        if all_sports_ready and event_start_local.date() > today:
            if self.REGISTRATION_DEADLINE > now:
                self.EVENT_STATUS = 'open'
                
            elif self.REGISTRATION_DEADLINE <= now:
                self.EVENT_STATUS = 'upcoming'
                

        # If all sports are ready and the event's start date has passed or is today, set status to 'ongoing'
        elif all_sports_ready and event_start_local.date() <= today:
            self.EVENT_STATUS = 'ongoing'
            


        self.save()
        













        
class TeamEvent(models.Model):
    TEAM_ID = models.ForeignKey(Team, on_delete=models.CASCADE)
    EVENT_ID = models.ForeignKey(Event, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['TEAM_ID', 'EVENT_ID'], name='unique_team_event')
        ]

    def __str__(self):
        return f"Team: {self.TEAM_ID.TEAM_NAME} - Event: {self.EVENT_ID.EVENT_NAME}"
    
class TeamCategory(models.Model):
    sport = models.ForeignKey(Sport, on_delete=models.CASCADE, related_name='categories', null=True, blank=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='team_categories', null=True, blank=True)  # Foreign key to Event
    name = models.CharField(max_length=50, null=True, blank=True)  # E.g., 'Junior', 'Senior', 'Midget'

    def __str__(self):
        return f"{self.name} - {self.sport} ({self.event.EVENT_NAME})"

class SportDetails(models.Model):
    ELIMINATION_CHOICES = [
        ('single', 'Single Elimination'),
        ('double', 'Double Elimination'),
    ]

    team_category = models.ForeignKey(TeamCategory, on_delete=models.CASCADE, related_name='sport_details', null=True, blank=True)  #TODO remove NULL/BLANK Link to TeamCategory
    number_of_teams = models.PositiveIntegerField(default=0)  # Total number of teams allowed for this sport in the event
    players_per_team = models.PositiveIntegerField(default=0)  # Number of players per team for this sport in the event
    entrance_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)],
        help_text="Entrance fee should be greater than or equal to 0.")  # Entrance fee (should be >= 0)
    elimination_type = models.CharField(max_length=10, choices=ELIMINATION_CHOICES,null=True)
    teams = models.ManyToManyField(Team, related_name='sport_details', blank=True)  # Teams registered for this sport in the event

    def __str__(self):
        return f"{self.team_category.name} - {self.team_category.sport.SPORT_NAME} ({self.team_category.event.EVENT_NAME})"

class Invoice(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)  # The individual registering (optional for team registrations)
    coach = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='team_invoices')  # The coach registering the team
    team = models.ForeignKey(Team, on_delete=models.CASCADE, null=True, blank=True)  # The team being registered (optional for individual registrations)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)  # The event being registered
    team_category = models.ForeignKey(TeamCategory, on_delete=models.CASCADE)  # Sport category in the event
    created_at = models.DateTimeField(auto_now_add=True)  # When the invoice was created
    is_paid = models.BooleanField(default=False)  # To track if payment has been made
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # Registration amount

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['team', 'event', 'team_category'], name='unique_team_event_registration'),
            models.UniqueConstraint(fields=['user', 'event', 'team_category'], name='unique_user_event_registration'),
        ]

    def __str__(self):
        if self.team:
            return f"Invoice for Team {self.team.TEAM_NAME} - {self.event.EVENT_NAME} ({self.team_category.name})"
        elif self.user:
            return f"Invoice for {self.user.username} - {self.event.EVENT_NAME} ({self.team_category.name})"
        else:
            return f"Invoice for {self.event.EVENT_NAME} ({self.team_category.name})"

class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    WALLET_BALANCE = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.user} - {self.WALLET_BALANCE}"

class WalletTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('refund', 'Refund'),
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        # Add other types as needed
    )
    
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    
    def __str__(self):
        return f"{self.transaction_type} of {self.amount} to {self.wallet.user} on {self.created_at} - {self.description}"


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



    

class Match(models.Model):
    ROUND_CHOICES = [
        ('First Round', 'First Round'),
        ('Quarter-finals', 'Quarter-finals'),
        ('Semi-finals', 'Semi-finals'),
        ('Finals', 'Finals'),
        ('Grand finals', 'Grand finals'),
    ]
    BRACKET_CHOICES = [
        ('Upper Bracket', 'Upper Bracket'),
        ('Lower Bracket', 'Lower Bracket'),
    ]

    sport_details = models.ForeignKey(SportDetails, on_delete=models.CASCADE, related_name='matches', null=True)
    team_a = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='team_a_matches', null=True)
    team_b = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='team_b_matches', null=True)
    round = models.CharField(max_length=50, choices=ROUND_CHOICES, null=True)
    bracket = models.CharField(max_length=50, choices=BRACKET_CHOICES, null=True)
    schedule = models.DateTimeField()  # Changed from date_time to schedule
    score_team_a = models.IntegerField(default=0)
    score_team_b = models.IntegerField(default=0)
    winner = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='won_matches')

    def __str__(self):
        return f"{self.team_a} vs {self.team_b} - {self.round}"

    class Meta:
        ordering = ['-schedule']  # Added negative sign for descending order

    def update_scores(self):
        if not self.sport_details or not self.sport_details.team_category or not self.sport_details.team_category.sport:
            raise AttributeError("SportDetails, TeamCategory, or Sport is missing.")

        sport_name = self.sport_details.team_category.sport.SPORT_NAME.strip().lower()

        # Initialize scores
        score_team_a = 0
        score_team_b = 0

        if sport_name == 'basketball':
            # Basketball: Sum the 'points' field for each team's players
            basketball_stats_a = BasketballStats.objects.filter(
                player_stats__match=self, player_stats__team=self.team_a
            )
            basketball_stats_b = BasketballStats.objects.filter(
                player_stats__match=self, player_stats__team=self.team_b
            )

            score_team_a = basketball_stats_a.aggregate(total_points=Sum('points'))['total_points'] or 0
            score_team_b = basketball_stats_b.aggregate(total_points=Sum('points'))['total_points'] or 0

        elif sport_name == 'volleyball':
            # Volleyball: Sum kills, blocks_score, and service_aces for each team's players
            volleyball_stats_a = VolleyballStats.objects.filter(
                player_stats__match=self, player_stats__team=self.team_a
            )
            volleyball_stats_b = VolleyballStats.objects.filter(
                player_stats__match=self, player_stats__team=self.team_b
            )

            score_team_a = volleyball_stats_a.aggregate(
                total_score=Sum('kills') + Sum('blocks_score') + Sum('service_aces')
            )['total_score'] or 0

            score_team_b = volleyball_stats_b.aggregate(
                total_score=Sum('kills') + Sum('blocks_score') + Sum('service_aces')
            )['total_score'] or 0

        # Update the match scores
        self.score_team_a = score_team_a
        self.score_team_b = score_team_b
        self.save()

        # Determine the winner
        if score_team_a > score_team_b:
            self.winner = self.team_a
        elif score_team_b > score_team_a:
            self.winner = self.team_b
        else:
            self.winner = None  # Draw

        self.save()




class PlayerStats(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='player_stats')
    player = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stats')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='player_stats')
    sport = models.ForeignKey(Sport, on_delete=models.CASCADE, related_name='player_stats')  # Link to sport

    class Meta:
        unique_together = ('player', 'match','team')

    def __str__(self):
        return f"{self.player} - {self.match} ({self.sport})"



class BasketballStats(models.Model):
    player_stats = models.OneToOneField(PlayerStats, on_delete=models.CASCADE, related_name='basketball_stats',null=True)
    points = models.IntegerField(default=0)
    rebounds = models.IntegerField(default=0)
    assists = models.IntegerField(default=0)
    blocks = models.IntegerField(default=0)
    steals = models.IntegerField(default=0)
    turnovers = models.IntegerField(default=0)
    three_pointers_made = models.IntegerField(default=0)
    free_throws_made = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.player_stats.player.username}'s Basketball Stats - Points: {self.points}, Rebounds: {self.rebounds}"


class VolleyballStats(models.Model):
    player_stats = models.OneToOneField(PlayerStats, on_delete=models.CASCADE, related_name='volleyball_stats',null=True)
    kills = models.IntegerField(default=0)
    blocks = models.IntegerField(default=0)
    blocks_score = models.IntegerField(default=0)
    digs = models.IntegerField(default=0)
    service_aces = models.IntegerField(default=0)
    attack_errors = models.IntegerField(default=0)
    reception_errors = models.IntegerField(default=0)
    assists = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.player_stats.player.username}'s Volleyball Stats - Kills: {self.kills}, Blocks: {self.blocks}"


class Subscription(models.Model):
    SUB_PLAN = models.CharField(max_length=50)
    SUB_DATE_STARTED = models.DateTimeField(default=timezone.now)
    SUB_DATE_END = models.DateTimeField()
    USER_ID = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.USER_ID.username} - {self.SUB_PLAN} (Started: {self.SUB_DATE_STARTED})"
    

class TeamRegistrationFee(models.Model): #TODO unused
    TEAM_ID = models.ForeignKey(Team, on_delete=models.CASCADE)
    MATCH_ID = models.ForeignKey(Match, on_delete=models.CASCADE)
    REGISTRATION_FEE = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    IS_PAID = models.BooleanField(default=False)

    def __str__(self):
        return f"Team: {self.TEAM_ID.TEAM_NAME} - Match: {self.MATCH_ID.MATCH_TYPE} - Paid: {self.IS_PAID}"
    

class SportsEvent(models.Model): # TODO unused
    EVENT_ID = models.OneToOneField(Event, on_delete=models.CASCADE, primary_key=True)
    SPORTS_ID = models.ForeignKey(Sport, on_delete=models.CASCADE)

    def __str__(self):
        return f"Event: {self.EVENT_ID.EVENT_NAME} - Sport: {self.SPORTS_ID.SPORT_NAME}"


class TeamMatch(models.Model):# TODO unused
    TEAM_ID = models.ForeignKey(Team, on_delete=models.CASCADE)
    MATCH_ID = models.ForeignKey(Match, on_delete=models.CASCADE)
    IS_WINNER = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['TEAM_ID', 'MATCH_ID'], name='unique_team_match')
        ]

    def __str__(self):
        return f"Team: {self.TEAM_ID.TEAM_NAME} - Match: {self.MATCH_ID.MATCH_TYPE} - Winner: {self.IS_WINNER}"


class UserMatch(models.Model):# TODO unused
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




class UserRegistrationFee(models.Model):# TODO unused
    USER_MATCH_ID = models.ForeignKey(UserMatch, on_delete=models.CASCADE)
    IS_PAID = models.BooleanField(default=False)

    def __str__(self):
        return f"UserMatch: {self.USER_MATCH_ID} - Paid: {self.IS_PAID}"


class Payment(models.Model):# TODO unused
    PAYMENT_AMOUNT = models.DecimalField(max_digits=10, decimal_places=2)
    PAYMENT_DATE = models.DateTimeField(default=timezone.now)
    WALLET_ID = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    SUBSCRIPTION_ID = models.ForeignKey(Subscription, on_delete=models.CASCADE, null=True, blank=True)
    TEAM_REGISTRATION_ID = models.ForeignKey(TeamRegistrationFee, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"Amount: {self.PAYMENT_AMOUNT} - Date: {self.PAYMENT_DATE}"


class Transaction(models.Model):# TODO unused
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
    user = models.ForeignKey(User, related_name='notifications', on_delete=models.CASCADE)  # recipient
    sender = models.ForeignKey(User, related_name='sent_notifications', on_delete=models.CASCADE, null=True, blank=True)
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    def __str__(self):
        user_username = self.user.username if self.user else 'Unknown'
        sender_username = self.sender.username if self.sender else 'Unknown'
        return f'Notification for {user_username} from {sender_username}: {self.message}'

    
class Invitation(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=50, default='Pending')  # Status can be Pending, Accepted, Declined
    sent_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Invitation to {self.user.username} for team {self.team.TEAM_NAME} - Status: {self.status}"
    

class PlayerRecruitment(models.Model):
    scout = models.ForeignKey(User, on_delete=models.CASCADE)
    player = models.ForeignKey(User, related_name='recruited_by', on_delete=models.CASCADE)
    is_recruited = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.scout.username} recruited {self.player.username}"


class BracketData(models.Model):
    sport_details = models.ForeignKey(SportDetails, on_delete=models.CASCADE, related_name="brackets",null=True)
    teams = models.JSONField()
    results = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Bracket for {self.sport_details.team_category.event.EVENT_NAME} - {self.sport_details.team_category.name}"
    
