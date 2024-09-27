from django.shortcuts import render, redirect
# from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views.generic import ListView
from .models import Sport, Team, Match, TeamParticipant, Event, VolleyballStats, Participant
from users.models import Profile
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.views import View
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
    return render (request, 'ligameet/eventorglandingpage.html', {'title': 'Event Organizer Landing Page'})

def player_dashboard(request):
    try:
        profile = request.user.profile
        if profile.role == 'Player':
            query = request.GET.get('q', '')
            match_type = request.GET.get('type', '')
            match_category = request.GET.get('category', '')

            # Fetch the participant linked to the logged-in user
            participant = Participant.objects.filter(USER_ID=request.user).first()
            
            # Get the team associated with the participant
            my_team = None
            if participant:
                team_participant = TeamParticipant.objects.filter(PART_ID=participant).select_related('TEAM_ID').first()
                my_team = team_participant.TEAM_ID if team_participant else None

            # Prefetch all participants for the team
            if my_team:
                my_team_participants = TeamParticipant.objects.filter(TEAM_ID=my_team).select_related('PART_ID__USER_ID')

            # Fetch Basketball and Volleyball Sport IDs
            basketball_sport = Sport.objects.filter(SPORT_NAME__iexact='Basketball').first()
            volleyball_sport = Sport.objects.filter(SPORT_NAME__iexact='Volleyball').first()

            # Fetch teams based on their SPORT_ID (basketball or volleyball)
            basketball_teams = Team.objects.filter(SPORT_ID=basketball_sport).prefetch_related(
                Prefetch('teamparticipant_set', queryset=TeamParticipant.objects.select_related('PART_ID__USER_ID'))
            )
            volleyball_teams = Team.objects.filter(SPORT_ID=volleyball_sport).prefetch_related(
                Prefetch('teamparticipant_set', queryset=TeamParticipant.objects.select_related('PART_ID__USER_ID'))
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
        
        # Create the event instance
        event = Event(
            EVENT_NAME=event_name,
            EVENT_DATE_START=event_date_start,
            EVENT_DATE_END=event_date_end,
            EVENT_LOCATION=event_location,
            EVENT_ORGANIZER=request.user,  # Set the current user as the organizer
            EVENT_STATUS='upcoming'  # Automatically set status
        )
        event.save()

        return JsonResponse({'success': True, 'event_name': event.EVENT_NAME})

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


def my_team_view(request):
    # Fetch the participant related to the logged-in user
    participant = TeamParticipant.objects.filter(PART_ID__USER_ID=request.user).first()
    
    # Get the team associated with the participant
    my_team = participant.TEAM_ID if participant else None
    
    context = {
        'my_team': my_team,
    }
    return render(request, 'ligameet/player_dashboard.html', context)