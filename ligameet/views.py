import base64
import traceback
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
# from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views.generic import ListView
from ligameet.forms import PlayerFilterForm, ScoutPlayerFilterForm, TeamRegistrationForm
from .models import *
from users.models import Profile
from django.utils.dateparse import parse_datetime
from django.core.files.base import ContentFile
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Prefetch
from django.db import transaction
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.db import IntegrityError
from chat.models import *
from django.db.models import Sum, Q
from .forms import  TeamCategoryForm, SportDetailsForm
from django.forms import modelformset_factory
from django.conf import settings
from paypal.standard.forms import PayPalPaymentsForm
from django.urls import reverse



def home(request):
    events = Event.objects.filter(IS_POSTED=True).exclude(EVENT_STATUS='cancelled').order_by('-EVENT_DATE_START')
    has_unread_messages = GroupMessage.objects.filter(
                group__members=request.user,
                is_read=False
            ).exists()
    context = {
                'events': events,
                'has_unread_messages': has_unread_messages,
            }
    return render(request, 'ligameet/home.html', context)

def about(request):
    return render(request, 'ligameet/about.html', {'title':'About'})

def landingpage(request):
    return render (request, 'ligameet/landingpage.html', {'title': 'Landing Page'})

@login_required
def event_dashboard(request): # TODO paginate
    try:
        profile = request.user.profile
        if profile.role == 'Event Organizer':
            # Fetch all events created by the logged-in user (event organizer)
            organizer_events = Event.objects.filter(EVENT_ORGANIZER=request.user).order_by('-EVENT_DATE_START')

            # Update the status of each event before rendering the page
            for event in organizer_events:
                event.update_status()  # Ensure the status is updated based on the current time

            # Fetch sports for the filtering dropdown
            sports = Sport.objects.all()

            has_unread_messages = GroupMessage.objects.filter(
                group__members=request.user,
                is_read=False
            ).exists()

            context = {
                'organizer_events': organizer_events,
                'sports': sports,
                'has_unread_messages': has_unread_messages,
            }
            return render(request, 'ligameet/events_dashboard.html', context)
        else:
            return redirect('home')

    except Profile.DoesNotExist:
        return redirect('home')




@login_required
def player_dashboard(request):
    try:
        profile = request.user.profile
        if profile.role == 'Player':
            chat_groups = ChatGroup.objects.all()
            # Fetch the selected sports for the player
            sport_profiles = SportProfile.objects.filter(USER_ID=request.user)
            selected_sports = [sp.SPORT_ID for sp in sport_profiles]

            query = request.GET.get('q', '')
            match_type = request.GET.get('type', '')
            match_category = request.GET.get('category', '')
            invitations = Invitation.objects.filter(user=request.user, status='Pending')
            participant = User.objects.filter(id=request.user.id).first()
            recent_activities = Activity.objects.filter(user=request.user).order_by('-timestamp')[:5]
            notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
            unread_notifications_count = notifications.filter(is_read=False).count()

            # Fetch all teams the player is part of
            my_teams = Team.objects.filter(teamparticipant__USER_ID=request.user).prefetch_related(
                Prefetch('teamparticipant_set', queryset=TeamParticipant.objects.select_related('USER_ID'))
            )
            
            # Create a list of dictionaries with team and its participants
            my_teams_and_participants = [
                {
                    'team': team,
                    'participants': TeamParticipant.objects.filter(TEAM_ID=team).select_related('USER_ID')
                }
                for team in my_teams
            ]

            # Filter teams and matches based on selected sports
            teams = Team.objects.filter(SPORT_ID__in=selected_sports).prefetch_related(
                Prefetch('teamparticipant_set', queryset=TeamParticipant.objects.select_related('USER_ID'))
            )
            basketball_teams = teams.filter(SPORT_ID__SPORT_NAME__iexact='Basketball')
            volleyball_teams = teams.filter(SPORT_ID__SPORT_NAME__iexact='Volleyball')

            if query:
                basketball_teams = basketball_teams.filter(TEAM_NAME__icontains=query)
                volleyball_teams = volleyball_teams.filter(TEAM_NAME__icontains=query)

            matches = Match.objects.filter(TEAM_ID__SPORT_ID__in=selected_sports)
            if match_type:
                matches = matches.filter(MATCH_TYPE__icontains=match_type)
            if match_category:
                matches = matches.filter(MATCH_CATEGORY__icontains=match_category)
            if query:
                matches = matches.filter(TEAM_ID__TEAM_NAME__icontains=query)

            context = {
                'basketball_teams': basketball_teams,
                'volleyball_teams': volleyball_teams,
                'matches': matches,
                'my_teams_and_participants': my_teams_and_participants,  # Pass the list here
                'recent_activities': recent_activities,
                'notifications': notifications,
                'unread_notifications_count': unread_notifications_count,
                'invitations': invitations,
                'chat_groups': chat_groups
            }
            return render(request, 'ligameet/player_dashboard.html', context)
        else:
            return redirect('home')
    except Profile.DoesNotExist:    
        return redirect('home')
    
@login_required
def join_team_request(request, team_id):
    team = get_object_or_404(Team, id=team_id)

    # Check if the team is full
    if team.teamparticipant_set.count() >= 30:
        messages.error(request, "This team is already full.")
        return redirect('player-dashboard')

    # Check if the user is already in the same team
    current_team_participant = TeamParticipant.objects.filter(USER_ID=request.user).first()

    if current_team_participant and current_team_participant.TEAM_ID == team:
        messages.warning(request, 'You are already a member of this team.')
        return redirect('player-dashboard')

    # Clean up any previously declined or removed requests for this team
    JoinRequest.objects.filter(USER_ID=request.user, TEAM_ID=team, STATUS='declined').delete()

    # Check if there's an active join request
    join_request = JoinRequest.objects.filter(USER_ID=request.user, TEAM_ID=team).first()
    if join_request:
        if join_request.STATUS == 'pending':
            messages.warning(request, 'You have already requested to join this team.')
            return redirect('player-dashboard')
        elif join_request.STATUS == 'approved':
            messages.warning(request, 'You are already approved to join this team.')
            return redirect('player-dashboard')

    # Create a new join request
    JoinRequest.objects.create(USER_ID=request.user, TEAM_ID=team, STATUS='pending')
    messages.success(request, 'Join request submitted successfully!')

    # Log activity
    Activity.objects.create(
        user=request.user,
        description=f"Requested to join the team {team.TEAM_NAME}"
    )
    
    return redirect('player-dashboard')




@csrf_exempt
@login_required
def mark_notification_read(request, notification_id):
    if request.method == 'POST':
        try:
            notification = Notification.objects.get(id=notification_id, user=request.user)
            notification.is_read = True
            notification.save()
            return JsonResponse({'message': 'Notification marked as read!'})
        except Notification.DoesNotExist:
            return JsonResponse({'message': 'Notification not found!'}, status=404)
    return JsonResponse({'message': 'Invalid request!'}, status=400)

@csrf_exempt
@login_required
def mark_all_notifications_as_read(request):
    if request.method == 'POST':
        notifications = Notification.objects.filter(user=request.user, is_read=False)
        notifications.update(is_read=True)
        return JsonResponse({'message': 'All notifications marked as read!'})
    return JsonResponse({'message': 'Invalid request!'}, status=400)


@csrf_exempt
@login_required
def poke_back(request, notification_id):
    if request.method == 'POST':
        try:
            notification = Notification.objects.get(id=notification_id, user=request.user)
            
            if 'poke' in notification.message:
                scout = notification.sender  # The scout is the sender of the original poke
                
                # Create poke-back notification for the scout
                poke_back_notification = Notification.objects.create(
                    user=scout,  # Correctly set the scout as the recipient
                    sender=request.user,  # The current user (player) is the sender
                    message=f"{request.user.username} has poked you back!",
                    created_at=timezone.now(),
                    is_read=False  # Unread by default
                )
                print(f"Notification created for scout: {poke_back_notification}")  # Debugging
                return JsonResponse({'message': 'Poke-back sent successfully!'})
            else:
                return JsonResponse({'message': 'Invalid notification type for poke-back!'}, status=400)
        except Notification.DoesNotExist:
            return JsonResponse({'message': 'Notification not found!'}, status=404)
    
    return JsonResponse({'message': 'Invalid request!'}, status=400)


def confirm_invitation(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        invitation_id = data.get('invitation_id')
        response = data.get('response')
        try:
            invitation = Invitation.objects.get(id=invitation_id)
            team = invitation.team  # Get the team associated with the invitation
            coach = team.COACH_ID  # Assuming COACH_ID is a foreign key to the coach's User model

            if response == 'Accept':
                # Check if the team is already full
                if team.teamparticipant_set.count() >= 30:
                    return JsonResponse({'message': 'Cannot accept invitation; team is full.'}, status=400)

                # Add the user to the team
                TeamParticipant.objects.create(
                    TEAM_ID=invitation.team,
                    USER_ID=invitation.user
                )
                invitation.status = 'Accepted'
                message = f"{invitation.user.username} accepted your invitation to join {team.TEAM_NAME}."
            elif response == 'Decline':
                invitation.status = 'Declined'
                message = f"{invitation.user.username} declined your invitation to join {team.TEAM_NAME}."
            
            invitation.save()

            # Create a notification for the coach
            Notification.objects.create(
                user=coach,
                message=message,
                created_at=timezone.now()
            )

            return JsonResponse({'message': f'Invitation {response.lower()}ed successfully!'})

        except Invitation.DoesNotExist:
            return JsonResponse({'message': 'Invitation not found'}, status=404)
        except Exception as e:
            return JsonResponse({'message': f'Error processing invitation: {str(e)}'}, status=500)

    return JsonResponse({'message': 'Invalid request'}, status=400)


@login_required
def event_details(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    event.update_status()
    sports_with_details = []

    # Loop through each sport associated with the event
    for sport in event.SPORT.all():
        try:
            sport_details = SportDetails.objects.get(sport=sport, event=event)

            # PayPal form configuration
            paypal_dict = {
                'business': settings.PAYPAL_RECEIVER_EMAIL,
                'amount': sport_details.entrance_fee,
                'item_name': f'Registration for {sport.SPORT_NAME} - {event.EVENT_NAME}',
                'invoice': f"{event.id}-{sport.id}",
                'currency_code': 'PHP',
                'notify_url': request.build_absolute_uri(reverse('paypal-ipn')),
                'return_url': request.build_absolute_uri(reverse('payment-success', args=[event.id, sport.SPORT_NAME])),
                'cancel_return': request.build_absolute_uri(reverse('payment-cancelled', args=[event_id])), #TODO add message and redirect to event-details
            }

            # Initialize PayPal form
            form = PayPalPaymentsForm(initial=paypal_dict)

            # Append sport details with the form
            sports_with_details.append({
                'sport': sport,
                'detail': sport_details,
                'paypal_form': form,
            })
        except SportDetails.DoesNotExist:
            # Handle case where no requirements exist for the sport
            sports_with_details.append({
                'sport': sport,
                'detail': None,
                'paypal_form': None,
            })

    context = {
        'event': event,
        'sports_with_details': sports_with_details,
    }

    return render(request, 'ligameet/event_details.html', context)



@login_required
def create_event(request):
    if request.method == 'POST':
        # Extracting the data from the request
        event_name = request.POST.get('EVENT_NAME')
        event_date_start = request.POST.get('EVENT_DATE_START')
        event_date_end = request.POST.get('EVENT_DATE_END')
        event_location = request.POST.get('EVENT_LOCATION')
        selected_sports = request.POST.getlist('SPORT')  # This should already return a list
        event_image = request.FILES.get('EVENT_IMAGE')  # Handle image upload
        contact_person = request.POST.get('CONTACT_PERSON')
        contact_phone = request.POST.get('CONTACT_PHONE')
        
        # Parse start and end datetime strings from the request if necessary
        event_date_start = parse_datetime(request.POST.get('EVENT_DATE_START'))
        event_date_end = parse_datetime(request.POST.get('EVENT_DATE_END'))

        # Check if there is an event with the same location where times overlap
        overlapping_event = Event.objects.filter(
            EVENT_LOCATION=event_location,
            EVENT_DATE_END__gt=event_date_start,  # Existing event ends after new event starts
            EVENT_DATE_START__lt=event_date_end   # Existing event starts before new event ends
        ).exists()

        # Check if an event with the same name already exists
        if Event.objects.filter(EVENT_NAME=event_name).exists():
            return JsonResponse({'success': False, 'error': 'An event with this name already exists.'})

        # If overlapping event exists, show an error message
        if overlapping_event:
            return JsonResponse({'success': False, 'error': 'An event is already scheduled at this location during the selected time range. Please choose a different time.'})

        # Create the event instance
        event = Event(
            EVENT_NAME=event_name,
            EVENT_DATE_START=event_date_start,
            EVENT_DATE_END=event_date_end,
            EVENT_LOCATION=event_location,
            EVENT_ORGANIZER=request.user,  # Set the current user as the organizer
            EVENT_IMAGE=event_image,  # Save the uploaded image
            CONTACT_PERSON=contact_person,
            CONTACT_PHONE=contact_phone
        )

        # Save the event first to get an ID
        event.save()

        # Associate selected sports with the event
        for sport_id in selected_sports:
            try:
                # Convert the sport_id to int if it's not already
                sport = Sport.objects.get(id=int(sport_id))  # Ensure the sport ID is an integer
                event.SPORT.add(sport)  # Add the sport to the event
                sport_requirement = SportDetails(
                    event=event,  # Link the requirement to the created event
                    sport=sport,  # Link the requirement to the sport
                )
                sport_requirement.save()  # Save the SportDetails instance

                # Create a TeamCategory for the sport and event
                team_category_junior = TeamCategory(
                    sport=sport,
                    event=event,
                    name='Junior'
                )
                team_category_junior.save()

                team_category_senior = TeamCategory(
                    sport=sport,
                    event=event,
                    name='Senior'
                )
                team_category_senior.save()

            except ValueError:
                # Handle if conversion fails, log or print for debugging
                print(f"Could not convert {sport_id} to int.")
                continue
            except Sport.DoesNotExist:
                print(f"Sport with ID {sport_id} does not exist.")
                continue  # Handle case where sport doesn't exist if necessary

        # Display a success message and return a JSON response after all sports are processed
        messages.success(request, f'Event {event_name} Created Successfully')
        return JsonResponse({'success': True, 'event_id': event.id})

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


@login_required
def edit_sport_details(request, event_id, sport_id):
    event = get_object_or_404(Event, id=event_id)
    sport = get_object_or_404(Sport, id=sport_id)
    sport_requirement, created = SportDetails.objects.get_or_create(sport=sport, event=event)
    sportname = sport.SPORT_NAME

    # Initialize forms for GET request
    sport_requirement_form = SportDetailsForm(instance=sport_requirement)
    team_category_form = TeamCategoryForm()

    # Handle POST request
    if request.method == 'POST':
        # Handle the SportDetails submission
        if 'sport_requirement_submit' in request.POST:
            sport_requirement_form = SportDetailsForm(request.POST, instance=sport_requirement)
            if sport_requirement_form.is_valid():
                # Save the SportDetails form
                sport_requirement = sport_requirement_form.save(commit=False)
                sport_requirement.event = event
                sport_requirement.sport = sport
                sport_requirement.save()

                # Save the selected category (ForeignKey instead of Many-to-Many)
                sport_requirement.allowed_category = sport_requirement_form.cleaned_data['allowed_category']
                sport_requirement.save()

                messages.success(request, f'{sportname} requirements updated successfully.')

                return redirect('event-details', event_id=event_id)
            else:
                messages.error(request, 'Please correct the errors in the sport requirement form.')

        # Handle the TeamCategoryForm submission
        elif 'team_category_submit' in request.POST:
            team_category_form = TeamCategoryForm(request.POST)
            if team_category_form.is_valid():
                # Save the new TeamCategory
                new_team_category = team_category_form.save(commit=False)
                new_team_category.sport = sport
                new_team_category.event = event
                new_team_category.save()

                messages.success(request, f'New team category "{new_team_category.name}" added successfully.')

                return redirect('edit-sport-details', event_id=event_id, sport_id=sport_id)

            else:
                messages.error(request, 'Please correct the errors in the team category form.')

    # Pass the selected category as initial data to the form
    sport_requirement_form.fields['allowed_category'].initial = sport_requirement.allowed_category

    # Filter team categories by event and sport to pass as context for the form
    sport_requirement_form.fields['allowed_category'].queryset = TeamCategory.objects.filter(
        event=event, sport=sport
    )

    context = {
        'event': event,
        'sport': sport,
        'sport_requirement_form': sport_requirement_form,
        'team_category_form': team_category_form,
    }

    return render(request, 'ligameet/edit_sport_details.html', context)


@login_required
def post_event(request, event_id):
    if request.method == 'POST':
        event = get_object_or_404(Event, id=event_id)
        if request.user == event.EVENT_ORGANIZER:
            event.IS_POSTED = 'True'  # Update with your status field
            event.save()
            messages.success(request, f'Event {event.EVENT_NAME} posted successfully!')
            return redirect('home')
    return redirect('event-details', event_id=event_id)

@login_required
def cancel_event(request, event_id):
    if request.method == 'POST':
        event = get_object_or_404(Event, id=event_id)

        if request.user == event.EVENT_ORGANIZER:
            event.EVENT_STATUS = 'cancelled'  # Update the event status to 'cancelled'
            event.save()

            # Add success message
            messages.success(request, 'Event Cancelled!')

            # Return a JSON response with the success message
            return JsonResponse({
                'success': True,
                'message': 'Event Cancelled!',
            })
            

        else:
            messages.error(request, 'You are not the organizer of this event.')
            return JsonResponse({
                'success': False,
                'message': 'You are not the organizer of this event.',
            })

    return JsonResponse({
        'success': False,
        'message': 'Invalid request method.',
    })





logger = logging.getLogger(__name__)

def is_coach(user):
    return hasattr(user, 'profile') and user.profile.role == 'Coach'





def leave_team(request, team_id):
    # Fetch the team by its ID
    team = get_object_or_404(Team, id=team_id)

    # Check if the user is a participant in the team
    try:
        participant = TeamParticipant.objects.get(USER_ID=request.user, TEAM_ID=team)
        participant.delete()  # Remove the participant from the team

        # Remove any join requests related to this team for the user
        JoinRequest.objects.filter(USER_ID=request.user, TEAM_ID=team).delete()

        messages.success(request, f'You have left the team {team.TEAM_NAME} successfully.')
        
        # Log the activity
        Activity.objects.create(
            user=request.user,
            description=f"Left the team {team.TEAM_NAME}"
        )
        
    except TeamParticipant.DoesNotExist:
        messages.warning(request, 'You are not a member of this team.')

    return redirect('player-dashboard')


@login_required
def scout_dashboard(request):
    try:
        profile = request.user.profile
        if profile.role == 'Scout':
            # Get all players (distinct) with role "Player"
            players = User.objects.filter(profile__role='Player').distinct()
            filter_form = ScoutPlayerFilterForm(request.GET)

            # Fetch notifications and count unread ones
            notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
            unread_notifications_count = notifications.filter(is_read=False).count()

            # Retrieve filter parameters from request
            search_query = request.GET.get('search', '').strip()
            position_filters = request.GET.getlist('position')
            selected_sport_id = request.GET.get('sport_id', '')

            # Apply sport filter if selected
            if selected_sport_id:
                players = players.filter(sportprofile__SPORT_ID__id=selected_sport_id)

            # Apply search query filter across username, first name, and last name
            if search_query:
                players = players.filter(
                    Q(username__icontains=search_query) |
                    Q(profile__FIRST_NAME__icontains=search_query) |
                    Q(profile__LAST_NAME__icontains=search_query)
                )

            # Define a mapping of sport IDs to position fields
            sport_position_map = {
                '1': 'bposition_played',  # Basketball
                '2': 'vposition_played',  # Volleyball
                # Add more sports as necessary
            }

            # Apply position filter based on the selected sport and position choices
            if position_filters and selected_sport_id in sport_position_map:
                position_field = sport_position_map[selected_sport_id]
                players = players.filter(
                    **{f"profile__{position_field}__in": position_filters}
                )

            # Get all available sports for the dropdown filter
            sports = Sport.objects.all()

            # Define sport-specific positions for the dropdown filter
            sport_positions = {
                'BASKETBALL': [
                    ['PG', 'Point Guard'],
                    ['SG', 'Shooting Guard'],
                    ['SF', 'Small Forward'],
                    ['PF', 'Power Forward'],
                    ['C', 'Center'],
                ],
                'VOLLEYBALL': [
                    ['OH', 'Outside Hitter'],
                    ['OPP', 'Opposite Hitter'],
                    ['SET', 'Setter'],
                    ['MB', 'Middle Blocker'],
                    ['LIB', 'Libero'],
                    ['DS', 'Defensive Specialist'],
                ],
                # Add more sports and positions as necessary
            }

            # Render the scout dashboard template with the context data
            return render(request, 'ligameet/scout_dashboard.html', {
                'title': 'Scout Dashboard',
                'players': players,
                'filter_form': filter_form,
                'sports': sports,
                'sport_positions': json.dumps(sport_positions),
                'selected_sport_id': selected_sport_id,
                'selected_positions': json.dumps(position_filters),  # Ensure it's a JSON string
                'notifications': notifications,
                'unread_notifications_count': unread_notifications_count,
            })
        else:
            # Redirect non-scouts to the homepage
            return redirect('home')
    except Profile.DoesNotExist:
        # Redirect if the user does not have a profile
        return redirect('home')




@csrf_exempt
@login_required
def poke(request, player_id):
    if request.method == 'POST':
        try:
            player = User.objects.get(id=player_id)
            scout = request.user  # The current user is the scout
            Notification.objects.create(
                user=player,  # The player is the recipient
                sender=scout,  # The scout is the sender
                message=f"You have been poked by {scout.username} (Scout)!",
                created_at=timezone.now(),
                is_read=False
            )
            return JsonResponse({'message': 'Poke sent successfully!'})
        except User.DoesNotExist:
            return JsonResponse({'message': 'Player not found!'}, status=404)
    return JsonResponse({'message': 'Invalid request!'}, status=400)



@login_required
def coach_dashboard(request):
    try:
        profile = request.user.profile
        if profile.role == 'Coach':
            # Get teams coached by the current user
            teams = Team.objects.filter(COACH_ID=request.user)
            # Get all chat groups for the teams
            chat_groups = ChatGroup.objects.filter(members__in=[request.user], team__in=teams)
            join_requests = JoinRequest.objects.filter(TEAM_ID__COACH_ID=request.user, STATUS='pending')

            # Get the coach's sport
            coach_profile = request.user.profile
            sport_profile = SportProfile.objects.filter(USER_ID=request.user).first()
            if not sport_profile:
                return redirect('home')  # Redirect if no sport is associated
            
            # Initialize the filter form
            filter_form = PlayerFilterForm(request.GET or None, coach=request.user)
            search_query = request.GET.get('search_query')
            position_filters = request.GET.getlist('position')
            
            notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
            unread_notifications_count = notifications.filter(is_read=False).count()

            # Build the player query based on search and position
            players = User.objects.filter(profile__role='Player')
            if sport_profile:
                players = players.filter(profile__sports__SPORT_ID=sport_profile.SPORT_ID)
                
            if search_query:
                players = players.filter(
                    models.Q(profile__FIRST_NAME__icontains=search_query) |
                    models.Q(profile__LAST_NAME__icontains=search_query) |
                    models.Q(username__icontains=search_query)
                )
                
            # Determine the position field based on the sport
            sport_name = sport_profile.SPORT_ID.SPORT_NAME.lower()
            position_field = 'profile__bposition_played' if sport_name == 'basketball' else 'profile__vposition_played'   
            
            if position_filters:
                players = players.filter(**{f"{position_field}__in": position_filters})
                
            players = players.select_related('profile').distinct()

            context = {
                'teams': teams,
                'players': players,
                'coach_profile': coach_profile,
                'join_requests': join_requests,
                'chat_groups': chat_groups,
                'filter_form': filter_form,
                'notifications': notifications,
                'unread_notifications_count': unread_notifications_count,
            }
            return render(request, 'ligameet/coach_dashboard.html', context)
        else:
            return redirect('home')
    except Profile.DoesNotExist:
        return redirect('home')

   

@login_required
def create_team(request):
    if request.method == 'POST':
        team_name = request.POST.get('teamName')
        team_type = request.POST.get('teamType')
        team_logo = request.FILES.get('teamLogo')  # Get the logo file

        # Check if user has a profile and is a coach
        try:
            coach_profile = Profile.objects.get(user=request.user)
            if coach_profile.role != 'Coach':  # Ensure the user is a coach
                return JsonResponse({'message': 'Only coaches can create teams.'}, status=403)
        except Profile.DoesNotExist:
            return JsonResponse({'message': 'User profile not found.'}, status=404)

        # Fetch the sport ID from SportProfile
        try:
            sport_profile = SportProfile.objects.get(USER_ID=request.user)
            sport_id = sport_profile.SPORT_ID.id
        except SportProfile.DoesNotExist:
            return JsonResponse({'message': 'Sport profile not found'}, status=400)

        # Check for duplicate team names
        if Team.objects.filter(TEAM_NAME__iexact=team_name, SPORT_ID_id=sport_id).exists():
            return JsonResponse({'message': 'A team with this name already exists for the selected sport.'}, status=400)

        # Proceed with team creation if no duplicate is found
        try:
            team = Team(
                TEAM_NAME=team_name,
                TEAM_TYPE=team_type,
                SPORT_ID_id=sport_id,
                COACH_ID=request.user,
                TEAM_LOGO=team_logo  # Save the uploaded logo
            )
            team.save()
            return JsonResponse({'message': 'Team created successfully!'})
        except IntegrityError:
            return JsonResponse({'message': 'Error creating team due to database integrity issues.'}, status=500)

    return JsonResponse({'message': 'Invalid request'}, status=400)



@login_required
def manage_team(request):
    if request.method == 'POST':
        team_id = request.POST.get('team_id')
        team_name = request.POST.get('manageTeamName')
        team_type = request.POST.get('manageTeamType')
        team_description = request.POST.get('manageTeamDescription')
        team_logo = request.FILES.get('teamLogo')  # Correct name for the file field

        try:
            team = Team.objects.get(id=team_id)
            team.TEAM_NAME = team_name
            team.TEAM_TYPE = team_type  
            team.TEAM_DESCRIPTION = team_description
            
            # Update the logo if a new one is uploaded
            if team_logo:
                team.TEAM_LOGO = team_logo

            team.save()
            
            # Include the updated logo URL in the JSON response
            team_logo_url = team.TEAM_LOGO.url if team.TEAM_LOGO else '/media/team_logo_images/default-logo.png'
            return JsonResponse({'message': 'Team updated successfully!', 'teamLogoUrl': team_logo_url})

        except Team.DoesNotExist:
            return JsonResponse({'message': 'Team not found'}, status=404)
        except Exception as e:
            print(f"Error updating team: {str(e)}")
            return JsonResponse({'message': f'Error updating team: {str(e)}'}, status=500)

    return JsonResponse({'message': 'Invalid request'}, status=400)


    
@login_required
def get_team_players(request):
    team_id = request.GET.get('team_id')
    team = get_object_or_404(Team, id=team_id)
    players = [{
        'id': participant.USER_ID.id,
        'name': participant.USER_ID.username
    } for participant in team.teamparticipant_set.all()]
    return JsonResponse({'players': players})


logger = logging.getLogger(__name__)

@login_required
@user_passes_test(is_coach, login_url='/login/')
def approve_join_request(request, join_request_id):
    join_request = get_object_or_404(JoinRequest, id=join_request_id)
    user = join_request.USER_ID
    team = join_request.TEAM_ID

    if join_request.STATUS == 'pending':
        try:
            join_request.STATUS = 'approved'
            join_request.save()
            logger.info(f"Join request for {user.username} to join {team.TEAM_NAME} approved.")

            # Add user to team if not already a participant
            team_participant, created = TeamParticipant.objects.get_or_create(USER_ID=user, TEAM_ID=team)

            if created:
                messages.success(request, f'{user.username} has been approved to join the team {team.TEAM_NAME}.')

                # Log activity
                Activity.objects.create(
                    user=user,
                    description=f"Approved to join the team {team.TEAM_NAME}"
                )
            else:
                logger.warning(f"User {user.username} is already a member of team {team.TEAM_NAME}.")
                messages.warning(request, f'{user.username} is already a member of the team {team.TEAM_NAME}.')

            # Send notification for approval in both cases
            notification = Notification.objects.create(
                user=user,
                message=f"Your request to join the team {team.TEAM_NAME} has been approved.",
                created_at=timezone.now(),
                is_read=False,
                sender=request.user
            )
            logger.info(f"Notification created for user {user.username}: {notification.message}")

        except Exception as e:
            logger.error(f"Error occurred while approving join request: {str(e)}")
            messages.error(request, 'An error occurred while processing the join request.')
    else:
        messages.warning(request, 'This join request has already been processed.')

    return redirect('coach-dashboard')



@user_passes_test(is_coach, login_url='/login/')
@login_required
def decline_join_request(request, join_request_id):
    join_request = get_object_or_404(JoinRequest, id=join_request_id)
    user = join_request.USER_ID
    team = join_request.TEAM_ID

    if join_request.STATUS == 'pending':
        join_request.STATUS = 'declined'
        join_request.save()

        # Send notification for decline
        Notification.objects.create(
            user=user,
            message=f"Your request to join the team {team.TEAM_NAME} has been declined.",
            created_at=timezone.now(),
            is_read=False,
            sender=request.user
        )

        messages.success(request, f'Join request from {user.username} declined.')
    else:
        messages.warning(request, 'This join request has already been processed.')

    return redirect('coach-dashboard')




@login_required
def remove_player_from_team(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            team_id = data.get('team_id')
            player_id = data.get('player_id')

            # Remove player from the team
            participant = TeamParticipant.objects.get(TEAM_ID=team_id, USER_ID=player_id)
            participant.delete()

            # Clean up any previous join requests for the same team
            JoinRequest.objects.filter(USER_ID=player_id, TEAM_ID=team_id).delete()

            # Send notification to the removed player
            Notification.objects.create(
                user_id=player_id,
                message=f"You have been removed from the team {participant.TEAM_ID.TEAM_NAME}.",
                created_at=timezone.now(),
                is_read=False,
                sender=request.user
            )

            return JsonResponse({'message': 'Player removed successfully!'})

        except TeamParticipant.DoesNotExist:
            return JsonResponse({'message': 'Player not found in team'}, status=404)
        except Exception as e:
            return JsonResponse({'message': f'Error removing player: {str(e)}'}, status=500)

    return JsonResponse({'message': 'Invalid request'}, status=400)



@login_required
def send_invite(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            team_id = data.get('team_id')
            invite_code = data.get('invite_code', '').strip()

            if not team_id or not invite_code:
                return JsonResponse({'message': 'Team ID and invite code are required'}, status=400)

            # Check the number of players in the team
            team = get_object_or_404(Team, id=team_id)
            if team.teamparticipant_set.count() >= 30:
                return JsonResponse({'message': 'Team is already full (maximum 30 players).'}, status=400)

            try:
                profile = Profile.objects.get(INV_CODE=invite_code)
                user = profile.user
            except Profile.DoesNotExist:
                return JsonResponse({'message': 'User with invite code not found'}, status=404)

            # Check if an invitation already exists
            if Invitation.objects.filter(team=team, user=user, status='Pending').exists():
                return JsonResponse({'message': 'An invitation is already pending for this user'}, status=400)

            # Create an invitation
            Invitation.objects.create(
                team=team,
                user=user,
                status='Pending'
            )
            return JsonResponse({'message': 'Invite sent successfully!'})

        except Exception as e:
            return JsonResponse({'message': f'Error sending invite: {str(e)}'}, status=500)

    return JsonResponse({'message': 'Invalid request'}, status=400)    

@login_required
def coach_mark_notification_read(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            notification_id = data.get('notification_id')
            notification = Notification.objects.get(id=notification_id, user=request.user)

            # Mark the notification as read
            notification.is_read = True
            notification.save()

            # Return success message
            return JsonResponse({'message': 'Notification marked as read'})
        except Notification.DoesNotExist:
            return JsonResponse({'message': 'Notification not found'}, status=404)
        except Exception as e:
            return JsonResponse({'message': f'Error: {str(e)}'}, status=500)

    return JsonResponse({'message': 'Invalid request'}, status=400)




@login_required
def delete_team(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        team_id = data.get('team_id')
        try:
            team = Team.objects.get(id=team_id)
            team.delete()
            return JsonResponse({'message': 'Team deleted successfully!'}, status=200)
        except Team.DoesNotExist:
            return JsonResponse({'message': 'Team not found'}, status=404)
        except Exception as e:
            return JsonResponse({'message': f'Error deleting team: {str(e)}'}, status=500)

    return JsonResponse({'message': 'Invalid request'}, status=400)



@login_required
def register(request, event_id, sport_id):
    event = get_object_or_404(Event, id=event_id)
    sport_requirement = get_object_or_404(SportDetails, event=event, sport__id=sport_id)
    entrance_fee = sport_requirement.entrance_fee

    # PayPal settings
    paypal_dict = {
        'business': settings.PAYPAL_RECEIVER_EMAIL,
        'amount': entrance_fee,
        'item_name': f'Registration for {sport_requirement.sport.SPORT_NAME}',
        'invoice': str(event_id) + "-" + str(sport_id),  # Unique invoice ID
        'currency_code': 'USD',
        'notify_url': request.build_absolute_uri(reverse('paypal-ipn')),  # PayPal will send IPN notifications here
        'return_url': request.build_absolute_uri(reverse('payment-success', args=[event_id, sport_id])),
        'cancel_return': request.build_absolute_uri(reverse('payment-cancelled', args=[event_id])),
    }

    form = PayPalPaymentsForm(initial=paypal_dict)
    context = {
        'event': event,
        'sport_requirement': sport_requirement,
        'form': form,
    }
    return render(request, 'ligameet/register.html', context)

# TODO backed for registering team in the event
def payment_success(request, event_id, sport_name):
    messages.success(request, f"Registered to {sport_name} successfully!")
    return redirect('event-details', event_id=event_id)

def payment_cancelled(request, event_id):
    messages.warning(request, "Payment was cancelled.")
    return redirect('event-details', event_id=event_id)




# View to handle registration
import logging
logger = logging.getLogger(__name__)

@login_required
def register_team(request, event_id):
    try:
        coach_id = request.user.id
        coach_name = request.user.get_full_name()

        # Retrieve the event object
        event = get_object_or_404(Event, id=event_id)

        # Retrieve the first sport ID associated with the event
        sport_id = event.SPORT.first().id if event.SPORT.exists() else None

        if not sport_id:
            return JsonResponse({
                'success': False,
                'message': 'Sport not found for the event.'
            })

        # Initialize the form with the coach and sport_id
        form = TeamRegistrationForm(initial={'sport_id': sport_id, 'coach_name': coach_name}, coach_id=coach_id, sport_id=sport_id)

        if request.method == 'POST':       
            form = TeamRegistrationForm(request.POST, coach_id=coach_id, sport_id=sport_id, coach_name=coach_name)
            
            if form.is_valid():
                team_name = form.cleaned_data['team_name']
                players = form.cleaned_data['players']

                # Get the existing team instance
                team = Team.objects.get(id=team_name.id)

                # Register the team for the event if not already registered
                team_event, created = TeamEvent.objects.get_or_create(
                    TEAM_ID=team,
                    EVENT_ID=event
                )
                print("Created:", created)

                sport = event.SPORT.first()

                # Update SportDetails if it exists
                sport_details = SportDetails.objects.filter(event=event).first()
                if sport_details:
                    sport_details.teams.add(team)
                    sport_details.sport = sport 
                    sport_details.save()
                else:
                    print("No SportDetails record found for the specified event.")

                # Message based on creation status
                if created:
                    # Assign players to the team only if this is a new event registration
                    for player in players:
                        TeamParticipant.objects.get_or_create(TEAM_ID=team, USER_ID=player)
                    message = 'Team registered successfully for the event.'
                else:
                    message = 'Team is already registered for this event.'

                # Retrieve players' names for the response
                player_names = [player.get_full_name() for player in players if player.get_full_name()]

                return JsonResponse({
                    'success': True,
                    'team_name': team.TEAM_NAME,
                    'players': player_names,
                    'message': message  # Ensure the message reflects the registration status
                })
                
            else:
                return JsonResponse({
                    'success': False,
                    'form_errors': form.errors
                })

        else:
            # GET request: instantiate the form with initial data
            form = TeamRegistrationForm(initial={'sport_id': sport_id, 'coach_name': coach_name}, coach_id=coach_id, sport_id=sport_id)

            return render(request, 'ligameet/event_details.html', {
                'form': form,
                'event': event,
                'sport_id': sport_id
            })

    except Event.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Event not found.'
        })
    except Sport.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Sport not found.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

        
import logging

logger = logging.getLogger(__name__)

def get_players(request, team_id):
    try:
        team = Team.objects.get(id=team_id, COACH_ID=request.user)
        players = team.teamparticipant_set.all()

        # Include player ID for checkbox values
        players_list = [
            {'id': player.USER_ID.id, 'name': f"{player.USER_ID.profile.FIRST_NAME} {player.USER_ID.profile.LAST_NAME}"}
            for player in players
        ]

        return JsonResponse({
            'success': True,
            'players': players_list,
        })
    except Team.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Team not found.'
        })




@login_required
def get_coach_name(request):
    # Get the logged-in user's profile
    profile = get_object_or_404(Profile, user=request.user)
    coach_name = f"{profile.FIRST_NAME} {profile.LAST_NAME}"
    
    # Return coach name as JSON
    return JsonResponse({'coach_name': coach_name})


@login_required
def get_teams(request):
    coach_id = request.user.id
    sport_id = request.GET.get('sport_id')
    
    teams = Team.objects.filter(COACH_ID=coach_id)
    if sport_id:
        teams = teams.filter(SPORT_ID=sport_id)
    
    teams_data = list(teams.values('id', 'TEAM_NAME'))
    return JsonResponse({'teams': teams_data})











    
