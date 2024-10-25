import json
from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.contrib import messages
# from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views.generic import ListView
from .models import *
from users.models import Profile
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Prefetch
from django.db import transaction
from django.views import View
import logging
from django.utils import timezone
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.db import IntegrityError
from chat.models import *
from .forms import EventForm 

def home(request):
    context = {
        'sports': Sport.objects.all()
    }
    return render(request, 'ligameet/home.html', context)

# class SportListView(LoginRequiredMixin,ListView):
class SportListView(ListView):
    model = Sport
    template_name = 'ligameet/home.html'
    context_object_name = 'sports'
    ordering = ['-EDITED_AT'] # - so that it displays the newest 

def about(request):
    return render(request, 'ligameet/about.html', {'title':'About'})

def landingpage(request):
    return render (request, 'ligameet/landingpage.html', {'title': 'Landing Page'})

def eventorglandingpage(request):
    # Fetch all events created by the logged-in user (event organizer)
    organizer_events = Event.objects.filter(EVENT_ORGANIZER=request.user).order_by('-EVENT_DATE_START')

    # Update the status of each event before rendering the page
    for event in organizer_events:
        event.update_status()  # Ensure the status is updated based on the current time

    # Filter for recent activity
    recent_activity = organizer_events[:5]  # Showing last 5 activities for simplicity

    # Fetch sports for the filtering dropdown
    sports = Sport.objects.all()

    # Handle the form submission
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)  # Include request.FILES for file uploads
        if form.is_valid():
            event = form.save(commit=False)  # Create an Event instance but don't save it yet
            event.EVENT_ORGANIZER = request.user  # Set the organizer
            event.save()  # Now save the event
            return redirect('your_success_url')  # Redirect to a success page or the same page
    else:
        form = EventForm()  # Create a blank form for GET requests

    # Apply filters if any are provided
    status_filter = request.GET.get('status')
    sport_filter = request.GET.get('sport')
    search_query = request.GET.get('search')

    if status_filter:
        organizer_events = organizer_events.filter(EVENT_STATUS=status_filter)
    
    if sport_filter:
        organizer_events = organizer_events.filter(SPORT__SPORT_CATEGORY=sport_filter)

    if search_query:
        organizer_events = organizer_events.filter(EVENT_NAME__icontains=search_query)

    context = {
        'organizer_events': organizer_events,
        'recent_activity': recent_activity,
        'sports': sports,
        'form': form,  # Pass the form to the template
    }
    
    return render(request, 'ligameet/events_dashboard.html', context)
    

@login_required
def player_dashboard(request):
    try:
        profile = request.user.profile
        if profile.role == 'Player':
            # Fetch the selected sports for the player
            sport_profiles = SportProfile.objects.filter(USER_ID=request.user)
            selected_sports = [sp.SPORT_ID for sp in sport_profiles]

            query = request.GET.get('q', '')
            match_type = request.GET.get('type', '')
            match_category = request.GET.get('category', '')
            invitations = Invitation.objects.filter(user=request.user, status='Pending')
            participant = User.objects.filter(id=request.user.id).first()
            recent_activities = Activity.objects.filter(user=request.user).order_by('-timestamp')[:3]
            notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
            unread_notifications_count = notifications.filter(is_read=False).count()
            my_team = None
            my_team_participants = []
            if participant:
                team_participant = TeamParticipant.objects.filter(USER_ID=participant).select_related('TEAM_ID').first()
                if team_participant:
                    my_team = team_participant.TEAM_ID
                    my_team_participants = TeamParticipant.objects.filter(TEAM_ID=my_team).select_related('USER_ID')
                    Activity.objects.create(
                        user=request.user,
                        description=f"Joined the team {my_team.TEAM_NAME}"
                    )
            
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
                'my_team': my_team,
                'recent_activities': recent_activities,
                'notifications': notifications,
                'unread_notifications_count': unread_notifications_count,
                'my_team_participants': my_team_participants,
                'invitations': invitations,
            }
            return render(request, 'ligameet/player_dashboard.html', context)
        else:
            return redirect('home')
    except Profile.DoesNotExist:
        return redirect('home')



def event_details(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    event.update_status()
    return render(request, 'ligameet/event_details.html', {'event': event})

@login_required
def create_event(request):
    if request.method == 'POST':
        event_name = request.POST.get('eventName')
        event_location = request.POST.get('pac-input')
        event_date_start = request.POST.get('eventDateStart')
        event_date_end = request.POST.get('eventDateEnd')
        sport_names = request.POST.getlist('eventSport')  # Get selected sports
        number_of_teams = request.POST.get('numberOfTeams')
        players_per_team = request.POST.get('playersPerTeam')
        payment_fee = request.POST.get('paymentFee')
        is_sponsored = request.POST.get('isSponsored') 
        contact_person = request.POST.get('contactPerson')
        contact_phone = request.POST.get('contactPhone')
        event_image = request.FILES.get('eventImage')  # Handle file upload

        # Create event instance
        event = Event(
            EVENT_NAME=event_name,
            EVENT_LOCATION=event_location,
            EVENT_DATE_START=event_date_start,
            EVENT_DATE_END=event_date_end,
            EVENT_ORGANIZER=request.user,
            NUMBER_OF_TEAMS=number_of_teams,
            PLAYERS_PER_TEAM=players_per_team,
            PAYMENT_FEE=payment_fee,
            IS_SPONSORED=is_sponsored,
            CONTACT_PERSON=contact_person,
            CONTACT_PHONE=contact_phone,
            EVENT_IMAGE=event_image,
        )

        # Save the event instance first
        event.save()

        # Associate the selected sports with the event
        for sport_name in sport_names:
            try:
                sport = Sport.objects.get(SPORT_NAME=sport_name)  # Assuming SPORT_NAME is unique
                event.SPORT.add(sport)  # Add the sport to the ManyToMany relationship
            except Sport.DoesNotExist:
                print(f"Sport not found: {sport_name}")  # Debugging print statement

        return JsonResponse({'success': True, 'event_id': event.id})

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})




logger = logging.getLogger(__name__)

def is_coach(user):
    return hasattr(user, 'profile') and user.profile.role == 'Coach'


@login_required
def join_team_request(request, team_id):
    team = get_object_or_404(Team, id=team_id)

    # Check if the team is full
    if team.teamparticipant_set.count() >= 30:
        messages.error(request, "This team is already full.")
        return redirect('player-dashboard')

    # Check if the user is currently in a team
    current_team_participant = TeamParticipant.objects.filter(USER_ID=request.user).first()
    
    # Case 1: The user is already in a team and it's not the same team
    if current_team_participant and current_team_participant.TEAM_ID != team:
        messages.warning(request, 'You are already a member of another team.')
        return redirect('player-dashboard')

    # Case 2: The user is trying to rejoin the same team they're already a part of
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

            # Use get_or_create to avoid duplicate entries
            team_participant, created = TeamParticipant.objects.get_or_create(USER_ID=user, TEAM_ID=team)

            if created:
                logger.info(f"User {user.username} added to team {team.TEAM_NAME}.")
                messages.success(request, f'{user.username} has been approved to join the team {team.TEAM_NAME}.')
                
                # Log activity
                Activity.objects.create(
                    user=user,
                    description=f"Approved to join the team {team.TEAM_NAME}"
                )
            else:
                logger.warning(f"User {user.username} is already a member of team {team.TEAM_NAME}.")
                messages.warning(request, f'{user.username} is already a member of the team {team.TEAM_NAME}.')
                
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
    if join_request.STATUS == 'pending':
        join_request.STATUS = 'declined'
        join_request.save()
        messages.success(request, f'Join request from {join_request.USER_ID.username} declined.')
    else:
        messages.warning(request, 'This join request has already been processed.')
    return redirect('coach-dashboard')

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
    sports = Sport.objects.all()
    players = []

    # Get the selected sport and search query from the GET request
    sport_id = request.GET.get('sport_id')
    search_query = request.GET.get('search', '').strip()  # Get search input and strip any whitespace

    if sport_id:
        # Filter players based on the selected sport
        players = User.objects.filter(
            teamparticipant__TEAM_ID__SPORT_ID=sport_id
        ).distinct()

        # If there's a search query, filter players further by their username or profile fields
        if search_query:
            players = players.filter(
                Q(username__icontains=search_query) |
                Q(profile__FIRST_NAME__icontains=search_query) |
                Q(profile__LAST_NAME__icontains=search_query)
            )

    return render(request, 'ligameet/scout_dashboard.html', {
        'title': 'Scout Dashboard',
        'sports': sports,
        'players': players
    })

@csrf_exempt
def poke_player(request):
    if request.method == 'POST':
        player_id = request.POST.get('player_id')
        
        # Retrieve the player based on the player_id
        player = User.objects.get(id=player_id)

        # Logic to notify the player (you can send an email, create a notification, etc.)
        # Create a notification for the player
        scout_name = request.user.get_full_name() or request.user.username
        notification = Notification.objects.create(
            user=player,
            message=f'You have been poked by {scout_name} (Scout)!'
        )
        # If you have an email notification system, you could also send an email here
        # send_mail(
        #     'You have a new poke!',
        #     'You have been poked by a scout.',
        #     'from@example.com',  # Replace with your sending email
        #     [player.user.email],  # The player's email
        #     fail_silently=False,
        # )

        return JsonResponse({'message': 'Player poked successfully!'})
    return JsonResponse({'message': 'Invalid request!'}, status=400)

@csrf_exempt
def mark_notification_read(request, notification_id):
    if request.method == 'POST':
        notification = Notification.objects.get(id=notification_id)
        notification.is_read = True
        notification.save()
        return JsonResponse({'message': 'Notification marked as read!'})
    return JsonResponse({'message': 'Invalid request!'}, status=400)

@csrf_exempt
def mark_all_notifications_as_read(request):
    if request.method == 'POST':
        notifications = Notification.objects.filter(user=request.user, is_read=False)
        notifications.update(is_read=True)
        
        return JsonResponse({'message': 'All notifications marked as read!'})
    
    return JsonResponse({'message': 'Invalid request!'}, status=400)

@login_required
def coach_dashboard(request):
    # Get teams coached by the current user
    teams = Team.objects.filter(COACH_ID=request.user)
    # Get all chat groups for the teams
    chat_groups = ChatGroup.objects.filter(members__in=[request.user], team__in=teams)
    join_requests = JoinRequest.objects.filter(TEAM_ID__COACH_ID=request.user, STATUS='pending')
    
    # Get the coach's sports
    coach_profile = request.user.profile
    selected_sports = SportProfile.objects.filter(USER_ID=request.user).values_list('SPORT_ID', flat=True)

    search_query = request.GET.get('search_query')
    
    if search_query:
        # Search for players by first name, last name, or username
        players = User.objects.filter(
            profile__role='Player',
            profile__sports__SPORT_ID__in=selected_sports
        ).filter(
            models.Q(profile__FIRST_NAME__icontains=search_query) |
            models.Q(profile__LAST_NAME__icontains=search_query) |
            models.Q(username__icontains=search_query)
        ).select_related('profile').distinct()
    else:
        # Fetch all players relevant to the coach's sports
        players = User.objects.filter(
            profile__role='Player',
            profile__sports__in=selected_sports
        ).select_related('profile').distinct()
    
    context = {
        'teams': teams,
        'players': players, 
        'coach_profile': coach_profile,
        'join_requests': join_requests,
        'chat_groups': chat_groups,  # Pass all chat groups
    }
    
    return render(request, 'ligameet/coach_dashboard.html', context)
   

@login_required
def create_team(request):
    if request.method == 'POST':
        # Get data from the form
        team_name = request.POST.get('teamName')
        team_type = request.POST.get('teamType')

        # Use the Profile associated with the logged-in user as the coach
        coach_profile = Profile.objects.get(user=request.user)  # Get the Profile of the logged-in user

        # Fetch the sport ID from SportProfile based on the logged-in user
        try:
            sport_profile = SportProfile.objects.get(USER_ID=request.user)
            sport_id = sport_profile.SPORT_ID.id
        except SportProfile.DoesNotExist:
            return JsonResponse({'message': 'Sport profile not found'}, status=400)

        # Create and save the new team
        try:
            team = Team(
                TEAM_NAME=team_name,
                TEAM_TYPE=team_type,
                SPORT_ID_id=sport_id,
                COACH_ID=coach_profile.user  # Assign the User instance here
            )
            team.save()
            return JsonResponse({'message': 'Team created successfully!'})
        except Exception as e:
            return JsonResponse({'message': f'Error creating team: {str(e)}'}, status=500)

    # Return an error if the request is not POST
    return JsonResponse({'message': 'Invalid request'}, status=400)

# @login_required
# def get_team_players(request):
#     team_id = request.GET.get('team_id')
#     try:
#         team = Team.objects.get(id=team_id)
#         players = [
#             {'id': participant.USER_ID.id, 'name': participant.USER_ID.username}
#             for participant in team.teamparticipant_set.all()
#         ]
#         return JsonResponse({'players': players})
#     except Team.DoesNotExist:
#         return JsonResponse({'message': 'Team not found'}, status=404)
    
@login_required
def get_team_players(request):
    team_id = request.GET.get('team_id')
    team = get_object_or_404(Team, id=team_id)
    players = [{
        'id': participant.USER_ID.id,
        'name': participant.USER_ID.username
    } for participant in team.teamparticipant_set.all()]
    return JsonResponse({'players': players})

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
            invite_name = data.get('invite_name', '').strip()

            if not team_id:
                return JsonResponse({'message': 'Team ID is required'}, status=400)

            # Check the number of players in the team
            team = get_object_or_404(Team, id=team_id)
            current_player_count = team.teamparticipant_set.count()
            if current_player_count >= 30:
                return JsonResponse({'message': 'Team is already full (maximum 30 players).'}, status=400)

            user = None
            if invite_code:
                try:
                    profile = Profile.objects.get(INV_CODE=invite_code)
                    user = profile.user
                except Profile.DoesNotExist:
                    return JsonResponse({'message': 'User with invite code not found'}, status=404)
            elif invite_name:
                user_query = User.objects.filter(
                    username__iexact=invite_name
                ) | User.objects.filter(
                    first_name__iexact=invite_name
                ) | User.objects.filter(
                    last_name__iexact=invite_name
                )
                if user_query.count() == 0:
                    return JsonResponse({'message': 'No users found with this name'}, status=404)
                elif user_query.count() > 1:
                    return JsonResponse({'message': 'Multiple users found with this name'}, status=400)
                user = user_query.first()
            else:
                return JsonResponse({'message': 'Invite code or name required'}, status=400)

            # Create an invitation
            invitation = Invitation.objects.create(
                team_id=team_id,
                user=user,
                status='Pending'
            )
            return JsonResponse({'message': 'Invite sent successfully!'})

        except Exception as e:
            return JsonResponse({'message': f'Error sending invite: {str(e)}'}, status=500)

    return JsonResponse({'message': 'Invalid request'}, status=400)



def confirm_invitation(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        invitation_id = data.get('invitation_id')
        response = data.get('response')
        try:
            invitation = Invitation.objects.get(id=invitation_id)
            team = invitation.team  # Get the team associated with the invitation
            
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
                invitation.save()
                return JsonResponse({'message': 'Invitation accepted successfully!'})
            elif response == 'Decline':
                invitation.status = 'Declined'
                invitation.save()
                return JsonResponse({'message': 'Invitation declined'})

        except Invitation.DoesNotExist:
            return JsonResponse({'message': 'Invitation not found'}, status=404)
        except Exception as e:
            return JsonResponse({'message': f'Error processing invitation: {str(e)}'}, status=500)

    return JsonResponse({'message': 'Invalid request'}, status=400)

@login_required
def manage_team(request):
    if request.method == 'POST':
        team_id = request.POST.get('team_id')
        team_name = request.POST.get('manageTeamName')
        team_type = request.POST.get('manageTeamType')
        team_description = request.POST.get('manageTeamDescription')

        try:
            team = Team.objects.get(id=team_id)
            team.TEAM_NAME = team_name
            team.TEAM_TYPE = team_type
            team.description = team_description
            team.save()
            return JsonResponse({'message': 'Team updated successfully!'})
        except Team.DoesNotExist:
            return JsonResponse({'message': 'Team not found'}, status=404)
        except Exception as e:
            return JsonResponse({'message': f'Error updating team: {str(e)}'}, status=500)

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
