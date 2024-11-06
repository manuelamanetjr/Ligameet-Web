import base64
import traceback
import json
from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.contrib import messages
# from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views.generic import ListView
from ligameet.forms import PlayerFilterForm, ScoutPlayerFilterForm
from .models import *
from users.models import Profile
from django.utils.dateparse import parse_datetime
from django.core.files.base import ContentFile
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Prefetch
from django.db import transaction
import logging
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.db import IntegrityError
from chat.models import *
from django.db.models import Q  # Import Q for more complex queries
from .forms import  TeamCategoryForm, SportRequirementForm


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

@login_required
def event_dashboard(request):
    try:
        profile = request.user.profile
        if profile.role == 'Event Organizer':
            # Fetch all events created by the logged-in user (event organizer)
            organizer_events = Event.objects.filter(EVENT_ORGANIZER=request.user).order_by('-EVENT_DATE_START')[:6]

            # Update the status of each event before rendering the page
            for event in organizer_events:
                event.update_status()  # Ensure the status is updated based on the current time

            # Fetch sports for the filtering dropdown
            sports = Sport.objects.all()

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
                'sports': sports,
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
                'chat_groups': chat_groups
            }
            return render(request, 'ligameet/player_dashboard.html', context)
        else:
            return redirect('home')
    except Profile.DoesNotExist:    
        return redirect('home')
    

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
def event_details(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    event.update_status()
    sports = event.SPORT.all()
    
    team_category_form = TeamCategoryForm()
    sport_requirement_forms = {}

    if request.method == 'POST':
        for sport in sports:
            sport_requirement_form = SportRequirementForm(request.POST, instance=sport_requirement)
            
            if sport_requirement_form.is_valid():
                sport_requirement_form.save()
                messages.success(request, f'Sport requirements updated successfully for {sport.SPORT_NAME}.')
                return redirect('event-details', event_id=event_id)
    else:
        for sport in sports:
            sport_requirement = SportRequirement.objects.filter(sport=sport, event=event).first()
            sport_requirement_forms[sport.id] = SportRequirementForm(instance=sport_requirement)

    context = {
        'event': event,
        'sports': sports,
        'team_category_form': team_category_form,
        'sport_requirement_forms': sport_requirement_forms,
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

        # Debugging output
        print(f"Selected Sports: {selected_sports}")  # Check what's being received

        # Check if an event with the same name already exists
        if Event.objects.filter(EVENT_NAME=event_name).exists():
            messages.warning(request, 'An event with this name already exists.')
            return JsonResponse({'success': False, 'error': 'An event with this name already exists.'})

        # Create the event instance
        event = Event(
            EVENT_NAME=event_name,
            EVENT_DATE_START=event_date_start,
            EVENT_DATE_END=event_date_end,
            EVENT_LOCATION=event_location,
            EVENT_ORGANIZER=request.user,  # Set the current user as the organizer
            EVENT_STATUS='upcoming',  # Automatically set status
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
                sport_requirement = SportRequirement(
                    event=event,  # Link the requirement to the created event
                    sport=sport,  # Link the requirement to the sport
                )
                sport_requirement.save()  # Save the SportRequirement instance

                # Create a TeamCategory for the sport and event
                team_category = TeamCategory(
                    sport=sport,  # Link the category to the sport
                    event=event,  # Link the category to the created event
                )
                team_category.save()  # Save the TeamCategory instance
            except ValueError:
                # Handle if conversion fails, log or print for debugging
                print(f"Could not convert {sport_id} to int.")
                continue
            except Sport.DoesNotExist:
                print(f"Sport with ID {sport_id} does not exist.")
                continue  # Handle case where sport doesn't exist if necessary

        return JsonResponse({'success': True, 'event_name': event.EVENT_NAME})

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
            players = User.objects.filter(profile__role='Player').distinct()
            filter_form = ScoutPlayerFilterForm(request.GET)
            
            # Poke back
            notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
            unread_notifications_count = notifications.filter(is_read=False).count()
            
            # Debugging print statements
            print(f"User: {request.user.username}, Profile Role: {profile.role}")
            print("Notifications for scout:", notifications)
            for notification in notifications:
                print(f"Notification: {notification.message}, is_read: {notification.is_read}")
 
                  
            
            # Get filter parameters
            search_query = request.GET.get('search', '').strip()
            position_filters = request.GET.getlist('position')
            selected_sport_id = request.GET.get('sport_id', '')

            # Apply sport filter if a sport is selected
            if selected_sport_id:
                players = players.filter(sportprofile__SPORT_ID__id=selected_sport_id)

            # Apply search query filter
            if search_query:
                players = players.filter(
                    Q(username__icontains=search_query) |
                    Q(profile__FIRST_NAME__icontains=search_query) |
                    Q(profile__LAST_NAME__icontains=search_query)
                )

            # Apply position filter if applicable
            if position_filters:
                players = players.filter(profile__position_played__in=position_filters)

            # Get all available sports for the sport filter dropdown
            sports = Sport.objects.all()

            # Dictionary for positions based on sport
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
            return redirect('home')
    except Profile.DoesNotExist:
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

            # Initialize the filter form
            filter_form = PlayerFilterForm(request.GET or None, coach=request.user)
            search_query = request.GET.get('search_query')
            position_filters = request.GET.getlist('position')

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
            if position_filters:
                players = players.filter(profile__position_played__in=position_filters)
            players = players.select_related('profile').distinct()

            context = {
                'teams': teams,
                'players': players,
                'coach_profile': coach_profile,
                'join_requests': join_requests,
                'chat_groups': chat_groups,
                'filter_form': filter_form,
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
        team_logo = request.FILES.get('manageTeamLogo')  # Get the new logo file, if any

        try:
            team = Team.objects.get(id=team_id)
            team.TEAM_NAME = team_name
            team.TEAM_TYPE = team_type  
            team.TEAM_DESCRIPTION = team_description
            
            # Update the logo if a new one is uploaded
            if team_logo:
                team.TEAM_LOGO = team_logo

            # Save the team instance
            team.save()
            
            return JsonResponse({'message': 'Team updated successfully!'})

        except Team.DoesNotExist:
            return JsonResponse({'message': 'Team not found'}, status=404)

        except Exception as e:
            # Log the error for debugging purposes (optional)
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


