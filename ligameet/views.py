from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.contrib import messages
# from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views.generic import ListView
from .models import *
from users.models import Profile
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.db import transaction
from django.views import View
import logging
from django.utils import timezone


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
    context = {
        'my_events': Event.objects.all()
    }
    return render(request, 'ligameet/eventorglandingpage.html', context)

def player_dashboard(request):
    try:
        profile = request.user.profile
        if profile.role == 'Player':
            query = request.GET.get('q', '')
            match_type = request.GET.get('type', '')
            match_category = request.GET.get('category', '')
            
            # Fetch the participant linked to the logged-in user
            participant = User.objects.filter(id=request.user.id).first()
            recent_activities = Activity.objects.filter(user=request.user).order_by('-timestamp')[:10]
            # Get the team associated with the participant through TeamParticipant
            my_team = None
            my_team_participants = []
            if participant:
                # Get the participant's team
                team_participant = TeamParticipant.objects.filter(USER_ID=participant).select_related('TEAM_ID').first()
            # Prefetch all participants for the team
                if team_participant:
                    my_team = team_participant.TEAM_ID  # Get the team from the TeamParticipant
                    # Get all participants of the team
                    my_team_participants = TeamParticipant.objects.filter(TEAM_ID=my_team).select_related('USER_ID')

            # Fetch Basketball and Volleyball Sport IDs
            basketball_sport = Sport.objects.filter(SPORT_NAME__iexact='Basketball').first()
            volleyball_sport = Sport.objects.filter(SPORT_NAME__iexact='Volleyball').first()

            # Fetch teams based on their SPORT_ID (basketball or volleyball)
            basketball_teams = Team.objects.filter(SPORT_ID=basketball_sport).prefetch_related(
                Prefetch('teamparticipant_set', queryset=TeamParticipant.objects.select_related('USER_ID'))
            )
            volleyball_teams = Team.objects.filter(SPORT_ID=volleyball_sport).prefetch_related(
                Prefetch('teamparticipant_set', queryset=TeamParticipant.objects.select_related('USER_ID'))
            )

            # Apply search query to team names if provided
            if query:
                basketball_teams = basketball_teams.filter(TEAM_NAME__icontains=query)
                volleyball_teams = volleyball_teams.filter(TEAM_NAME__icontains=query)

            # Fetch and filter matches
            matches = Match.objects.all()
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
                'my_team_participants': my_team_participants,  # Pass all participants to context
            }

            return render(request, 'ligameet/player_dashboard.html', context)
        else:
            return redirect('home')
    except Profile.DoesNotExist:
        return redirect('home')
    
@login_required
def create_event(request):
    if request.method == 'POST':
        event_name = request.POST.get('eventName')
        event_date_start = request.POST.get('eventDateStart')
        event_date_end = request.POST.get('eventDateEnd')
        event_location = request.POST.get('eventLocation')
        sport_id = request.POST.get('sportId')  # Get the sport ID

        # Assuming you have a Sport model and are retrieving it
        sport = Sport.objects.get(id=sport_id)  # Fetch the sport object

        # Create the event instance
        event = Event(
            EVENT_NAME=event_name,
            EVENT_DATE_START=event_date_start,
            EVENT_DATE_END=event_date_end,
            EVENT_LOCATION=event_location,
            EVENT_ORGANIZER=request.user,  # Set the current user as the organizer
            EVENT_STATUS='upcoming',  # Automatically set status
            SPORT_ID=sport  # Associate the sport
        )
        event.save()

        return JsonResponse({'success': True, 'event_name': event.EVENT_NAME})

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

logger = logging.getLogger(__name__)

def join_team_request(request, team_id):
    # Fetch the team by its ID
    team = get_object_or_404(Team, id=team_id)
    
    # Check if a join request already exists for this user and team
    join_request = JoinRequest.objects.filter(USER_ID=request.user, TEAM_ID=team).first()

    if join_request:
        if join_request.STATUS == 'pending':
            messages.warning(request, 'You have already requested to join this team.')
            return redirect('player-dashboard')
        elif join_request.STATUS == 'approved':
            messages.warning(request, 'You are already approved to join this team.')
            return redirect('player-dashboard')
    
    # Create a new join request if not already submitted
    join_request = JoinRequest.objects.create(USER_ID=request.user, TEAM_ID=team, STATUS='pending')
    messages.success(request, 'Join request submitted successfully!')
    
    # Log the activity
    Activity.objects.create(
        user=request.user,
        description=f"Requested to join the team {team.TEAM_NAME}"
    )

    return redirect('player-dashboard')

def approve_join_request(request, join_request_id):
    # Fetch the join request or raise a 404 error if not found
    join_request = get_object_or_404(JoinRequest, id=join_request_id)
    user = join_request.USER_ID
    team = join_request.TEAM_ID

    # Check if the join request is pending
    if join_request.STATUS == 'pending':
        try:
            # Approve the join request
            join_request.STATUS = 'approved'
            join_request.save()

            logger.info(f"Join request for {user.username} to join {team.TEAM_NAME} approved.")

            # Check if the user is already a participant
            if not TeamParticipant.objects.filter(USER_ID=user, TEAM_ID=team).exists():
                # Create a TeamParticipant entry
                TeamParticipant.objects.create(USER_ID=user, TEAM_ID=team)
                logger.info(f"User {user.username} added to team {team.TEAM_NAME}.")
                messages.success(request, f'{user.username} has been approved to join the team {team.TEAM_NAME}.')
                
                # Log the activity
                Activity.objects.create(
                    user=user,
                    description=f"Approved to join the team {team.TEAM_NAME}")
                
            else:
                logger.warning(f"User {user.username} is already a member of team {team.TEAM_NAME}.")
                messages.warning(request, f'{user.username} is already a member of the team {team.TEAM_NAME}.')

        except Exception as e:
            logger.error(f"Error occurred while approving join request: {str(e)}")
            messages.error(request, 'An error occurred while processing the join request.')
    else:
        messages.warning(request, 'This join request has already been processed.')

    return redirect('player-dashboard')

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

