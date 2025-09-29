import os
from django.shortcuts import get_object_or_404, render, redirect
from django.db import transaction
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash 
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from .forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm, PlayerForm, VolleyBallForm, BasketBallForm
from .models import Profile, SportProfile, User
from ligameet.models import Sport, Event, Invitation, TeamParticipant, Team, JoinRequest
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import random
import string
import smtplib
from email.message import EmailMessage

from django.conf import settings
from paypal.standard.forms import PayPalPaymentsForm
from django.urls import reverse
import uuid
from datetime import datetime
from django.core.exceptions import ObjectDoesNotExist
import logging
from django.utils import timezone


@csrf_exempt
def register_user(request):
    if request.method == 'POST':
        body = json.loads(request.body)
        email = body.get('email')
        username = body.get('username')
        password = body.get('password')

        # Check if user already exists
        from .models import User, Profile
        if User.objects.filter(email=email).exists():
            print(f"User with email {email} already exists")
            return JsonResponse({'error': 'User with this email already exists'}, status=400)
        
        if User.objects.filter(username=username).exists():
            print(f"User with username {username} already exists")
            return JsonResponse({'error': 'User with this username already exists'}, status=400)

        try:
            with transaction.atomic():
                print(f"Starting user registration for {username}")
                
                # Hash password using Django's function
                hashed_password = make_password(password)

                # Create the user first
                user = User.objects.create(
                    email=email,
                    username=username,
                    password=hashed_password,
                    first_name='',
                    last_name='',
                    is_superuser=False,
                    is_staff=False,
                    is_active=True,
                    date_joined='2024-10-15T10:00:00Z',
                    last_login=None
                )
                print(f"User created with ID: {user.id}")

                # Delete any existing profile for this user (shouldn't happen, but just in case)
                Profile.objects.filter(user_id=user.id).delete()
                print(f"Cleaned up any existing profiles for user {user.id}")

                # Create Profile with Player role
                profile = Profile.objects.create(
                    user=user,
                    role='Player'
                )
                print(f"Profile created with ID: {profile.id} for user {user.username}")

            print(f"User {username} registered successfully with Player role")
            return JsonResponse({'message': 'User registered successfully in Django'})
            
        except Exception as e:
            print(f"Error during registration: {str(e)}")
            # If we get here, the transaction has been rolled back
            return JsonResponse({'error': f'Registration failed: {str(e)}'}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def login_user(request):
    if request.method == 'POST':
        body = json.loads(request.body)
        email = body.get('email')
        password = body.get('password')
        
        print(f"Received login attempt with email: {email}")
        
        user = User.objects.filter(email=email).first()
        if user is None:
            print("User not found in the database")
            return JsonResponse({'error': 'Invalid login credentials'}, status=400)
        else:
            print("User found in the database")
        
        # Check if the password is correct
        if not check_password(password, user.password):
            print("Password check failed")
            return JsonResponse({'error': 'Invalid login credentials'}, status=400)
        
        # Ensure the user has the 'Player' role
        profile = Profile.objects.filter(user=user).first()
        if profile is None:
            print("User does not have a profile")
            return JsonResponse({'error': 'User profile not found'}, status=403)
        
        # Check if user has Player role
        if profile.role != 'Player':
            print(f"Access denied: User has role {profile.role}, but only Players can log in")
            return JsonResponse({'error': 'Access denied: Only Players can log in'}, status=403)
        
        print(f"User logged in successfully with role: {profile.role}")
        return JsonResponse({
            'message': 'User logged in successfully',
            'role': profile.role
        })
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)


def get_sports(request):
    sports = Sport.objects.values('id', 'SPORT_NAME', 'IMAGE')  # Include the fields you need
    # Add the full URL for the image
    for sport in sports:
        if sport['IMAGE']:
            sport['IMAGE'] = request.build_absolute_uri(sport['IMAGE'])
    return JsonResponse(list(sports), safe=False)



@csrf_exempt
def update_user_sport(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            sport_name = data.get('sport_name')

            user = User.objects.get(id=user_id)
            profile = Profile.objects.get(user=user)
            
            sport = Sport.objects.get(SPORT_NAME=sport_name)
            profile.sports.add(sport)
            profile.save()

            return JsonResponse({'message': 'Sport added successfully'}, status=200)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request method'}, status=400)



@csrf_exempt
def get_events(request):
    if request.method == 'GET':
        events = Event.objects.all()
        events_list = []

        for event in events:
            events_list.append({
                'id': event.id,
                'name': event.EVENT_NAME,
                'date_start': event.EVENT_DATE_START,
                'date_end': event.EVENT_DATE_END,
                'location': event.EVENT_LOCATION,
                'status': event.EVENT_STATUS,
                'organizer': event.EVENT_ORGANIZER.username,
                'image': request.build_absolute_uri(event.EVENT_IMAGE.url) if event.EVENT_IMAGE else None,
                'sports': [sport.SPORT_NAME for sport in event.SPORT.all()],
                'payment_fee': str(event.PAYMENT_FEE),
                'is_sponsored': event.IS_SPONSORED,
                'contact_person': event.CONTACT_PERSON,
                'contact_phone': event.CONTACT_PHONE,
                'registration_deadline': event.REGISTRATION_DEADLINE,
            })

        return JsonResponse(events_list, safe=False)

    return JsonResponse({'error': 'Invalid request method'}, status=400)




@csrf_exempt
def get_invitations(request, user_id):
    if request.method == 'GET':
        invitations = Invitation.objects.filter(user_id=user_id)
        invitations_list = []

        for invitation in invitations:
            invitations_list.append({
                'id': invitation.id,
                'team_name': invitation.team.TEAM_NAME,
                'status': invitation.status,
                'sent_at': invitation.sent_at,
                'confirmed_at': invitation.confirmed_at,
            })

        return JsonResponse(invitations_list, safe=False)

    return JsonResponse({'error': 'Invalid request method'}, status=400)








@csrf_exempt
def update_invitation_status(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            invitation_id = data.get('invitation_id')
            status = data.get('status')

            if not invitation_id or not status:
                return JsonResponse({'error': 'Missing invitation_id or status'}, status=400)

            if status not in ['Pending', 'Accepted', 'Declined']:
                return JsonResponse({'error': 'Invalid status value'}, status=400)

            invitation = Invitation.objects.get(id=invitation_id)
            invitation.status = status

            if status == 'Accepted' and not invitation.confirmed_at:
                invitation.confirmed_at = timezone.now()  # Set the confirmation time when accepted
                invitation.save()

                # Add the user to the team after accepting the invitation
                team = invitation.team  # Get the team associated with the invitation
                user = invitation.user  # Get the user associated with the invitation
                
                # Ensure the user is not already a participant in the team
                if not TeamParticipant.objects.filter(USER_ID=user, TEAM_ID=team).exists():
                    # Add the user as a participant in the team
                    TeamParticipant.objects.create(USER_ID=user, TEAM_ID=team)
                
                response_data = {'message': 'Invitation status updated and user added to team'}
                return JsonResponse(response_data, status=200)

            invitation.save()  # Save if the status is not accepted

            response_data = {'message': 'Invitation status updated successfully'}
            return JsonResponse(response_data, status=200)

        except Invitation.DoesNotExist:
            return JsonResponse({'error': 'Invitation not found'}, status=404)
        except Exception as e:
            print(f"Error accepting invitation: {e}")
            return JsonResponse({'error': 'An error occurred'}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=400)




@csrf_exempt
def fetch_account_details(request):
    if request.method == 'GET':
        user_id = request.GET.get('user_id')
        if not user_id:
            return JsonResponse({'error': 'user_id is required'}, status=400)
        try:
            user = User.objects.get(id=user_id)
            profile = Profile.objects.get(user=user)

            account_details = {
                'username': user.username,
                'email': user.email,
                'first_name': profile.FIRST_NAME,
                'last_name': profile.LAST_NAME,
                'middle_name': profile.MIDDLE_NAME,
                'date_of_birth': profile.DATE_OF_BIRTH,
                'gender': profile.GENDER,
                'address': profile.ADDRESS,
                'height': profile.HEIGHT,
                'weight': profile.WEIGHT,
                'phone': profile.PHONE,
                'role': profile.role,
                'image_url': request.build_absolute_uri(profile.image.url) if profile.image else None,
                'sports': [sport.SPORT_ID.SPORT_NAME for sport in profile.sports.all()],
                'has_selected_sport': profile.sports.exists(),
            }
            return JsonResponse({'account_details': account_details}, status=200)
        except ObjectDoesNotExist:
            logger.error(f"User or Profile not found for user_id: {user_id}")
            return JsonResponse({'error': 'User or Profile not found'}, status=404)
        except Exception as e:
            logger.error(f"Error fetching account details: {e}")
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request method'}, status=400)



logger = logging.getLogger(__name__)

@csrf_exempt
def update_account_details(request):
    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            if not user_id:
                return JsonResponse({'error': 'user_id is required'}, status=400)

            profile = Profile.objects.select_related('user').get(user__id=user_id)
            updatable_fields = ['FIRST_NAME', 'LAST_NAME', 'MIDDLE_NAME', 'GENDER', 'ADDRESS', 'PHONE']
            for field in updatable_fields:
                setattr(profile, field, data.get(field.lower(), getattr(profile, field)))

            # Parse date
            if data.get('date_of_birth'):
                profile.DATE_OF_BIRTH = datetime.strptime(data['date_of_birth'], '%Y-%m-%dT%H:%M:%S.%fZ').date()

            profile.save()
            return JsonResponse({'status': 'success'}, status=200)
        except ObjectDoesNotExist:
            logger.error("User or Profile not found for update")
            return JsonResponse({'status': 'error', 'message': 'User or Profile not found'}, status=404)
        except Exception as e:
            logger.error(f"Error updating profile: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request method'}, status=400)



@csrf_exempt
def fetch_teams(request):
    if request.method == 'GET':
        user_id = request.GET.get('user_id')
        if not user_id:
            return JsonResponse({'error': 'user_id is required'}, status=400)

        try:
            profile = Profile.objects.get(user_id=user_id)
            sport_profiles = SportProfile.objects.filter(profile=profile)

            if not sport_profiles.exists():
                return JsonResponse({'teams': []}, status=200)

            selected_sports = sport_profiles.values_list('SPORT_ID', flat=True)
            teams = Team.objects.filter(SPORT_ID__in=selected_sports).prefetch_related('teamparticipant_set', 'COACH_ID')

            teams_data = [
                {
                    'id': team.id,
                    'name': team.TEAM_NAME,
                    'type': team.TEAM_TYPE,
                    'coach': team.COACH_ID.username if team.COACH_ID else None,
                    'description': team.TEAM_DESCRIPTION,
                    'logo_url': request.build_absolute_uri(team.TEAM_LOGO.url) if team.TEAM_LOGO else None,
                    'members': [
                        {"id": member.USER_ID.id, "name": member.USER_ID.username}
                        for member in team.teamparticipant_set.all()
                    ],
                }
                for team in teams
            ]

            return JsonResponse({'teams': teams_data}, status=200)

        except Profile.DoesNotExist:
            return JsonResponse({'error': 'User or Profile not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=400)



@csrf_exempt
def join_team(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        team_id = request.POST.get('team_id')

        try:
            user = User.objects.get(id=user_id)
            team = Team.objects.get(id=team_id)

            # Check if a join request already exists
            if JoinRequest.objects.filter(USER_ID=user, TEAM_ID=team).exists():
                return JsonResponse({'error': 'You already have a pending join request for this team.'}, status=400)

            # Create a new join request
            join_request = JoinRequest(USER_ID=user, TEAM_ID=team, STATUS='pending')
            join_request.save()

            return JsonResponse({'message': 'Join request sent successfully.'}, status=200)

        except User.DoesNotExist:
            return JsonResponse({'error': 'Invalid user ID.'}, status=404)
        except Team.DoesNotExist:
            return JsonResponse({'error': 'Invalid team ID.'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method.'}, status=405)



@csrf_exempt
def team_leave(request):
    if request.method == 'POST':
        try:
            # Parse the JSON body
            data = json.loads(request.body)

            # Extract user_id and team_id
            user_id = data.get('user_id')
            team_id = data.get('team_id')

            if not user_id or not team_id:
                return JsonResponse({'error': 'user_id and team_id are required.'}, status=400)

            # Validate if the user exists
            user = User.objects.get(id=user_id)

            # Validate if the team exists
            team = Team.objects.get(id=team_id)

            # Check if the user is a participant in the team
            participant = TeamParticipant.objects.filter(USER_ID=user, TEAM_ID=team).first()
            if not participant:
                return JsonResponse({'error': 'You are not a participant in this team.'}, status=400)

            # Remove the participant
            participant.delete()

            # Remove any related join requests
            JoinRequest.objects.filter(USER_ID=user, TEAM_ID=team).delete()

            return JsonResponse({'message': 'Successfully left the team and removed related join requests.'}, status=200)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON input.'}, status=400)
        except User.DoesNotExist:
            return JsonResponse({'error': 'Invalid user ID.'}, status=404)
        except Team.DoesNotExist:
            return JsonResponse({'error': 'Invalid team ID.'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method.'}, status=405)






##################################################################################################################################################################################################################################################################
#     MOBILE     MOBILE     MOBILE     MOBILE     MOBILE     MOBILE     MOBILE     MOBILE     MOBILE     MOBILE     MOBILE     MOBILE     MOBILE     MOBILE     MOBILE     MOBILE     MOBILE     MOBILE     MOBILE     MOBILE     MOBILE     MOBILE     MOBILE   # 
##################################################################################################################################################################################################################################################################


def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Your account has been created! You are now able to log in')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'users/register.html', {'form': form})

@login_required
def view_profile(request, username):
    user = get_object_or_404(User, username=username)
    profile = get_object_or_404(Profile, user=user)  # Get the Profile associated with the user
    return render(request, 'users/view_profile.html', {'profile': profile})


@login_required
def profile(request):
    user_profile = request.user.profile
    selected_sports = user_profile.sports.all()
    
    has_basketball = selected_sports.filter(SPORT_ID__SPORT_NAME__iexact='Basketball').exists()
    has_volleyball = selected_sports.filter(SPORT_ID__SPORT_NAME__iexact='Volleyball').exists()

    # Initialize all forms
    u_form = UserUpdateForm(instance=request.user)
    p_form = ProfileUpdateForm(instance=user_profile)
    player_form = PlayerForm(instance=user_profile)
    basketball_form = BasketBallForm(instance=user_profile)
    volleyball_form = VolleyBallForm(instance=user_profile)
    
    if request.method == 'POST':
        form_id = request.POST.get('form_id')

        if form_id == 'personalForm':
            u_form = UserUpdateForm(request.POST, instance=request.user)
            p_form = ProfileUpdateForm(request.POST, request.FILES, instance=user_profile)
            if u_form.is_valid() and p_form.is_valid():
                u_form.save()
                p_form.save()
                messages.success(request, 'Your personal information has been updated!')
                return redirect('profile')

        elif form_id == 'playerForm':
            player_form = PlayerForm(request.POST, instance=user_profile)
            if player_form.is_valid():
                player_form.save()
                messages.success(request, 'Your player information has been updated!')
                return redirect('profile')

        elif form_id == 'basketballForm':
            basketball_form = BasketBallForm(request.POST, instance=user_profile)
            if basketball_form.is_valid():
                basketball_form.save()
                messages.success(request, 'Your basketball information has been updated!')
                return redirect('profile')

        elif form_id == 'volleyballForm':
            volleyball_form = VolleyBallForm(request.POST, instance=user_profile)
            if volleyball_form.is_valid():
                volleyball_form.save()
                messages.success(request, 'Your volleyball information has been updated!')
                return redirect('profile')

    context = {
        'u_form': u_form,
        'p_form': p_form,
        'player_form': player_form,
        'basketball_form': basketball_form,
        'volleyball_form': volleyball_form,
        'user_profile': user_profile,
        'has_basketball': has_basketball,
        'has_volleyball': has_volleyball,
    }
    return render(request, 'users/profile.html', context)



def choose_role(request):
    profile, created = Profile.objects.get_or_create(user=request.user)

    # Fetch all sports from the database
    sports = Sport.objects.all()
    paypal_form = None

    if request.method == 'POST':
        role = request.POST.get('role')
        sports_selected = request.POST.get('sports').split(',') if request.POST.get('sports') else []

        # Update the user's role
        profile.role = role
        profile.sports.clear()
        
        # Handle the Coach role
        if role == 'Coach' and len(sports_selected) > 1:
            sports_selected = sports_selected[:1]  # Allow only one sport for Coach

        # Only attempt to add sports if any were selected            
        for sport_name in sports_selected:
            try:
                sport = Sport.objects.get(SPORT_NAME__iexact=sport_name)
                sport_profile, created = SportProfile.objects.get_or_create(USER_ID=request.user, SPORT_ID=sport)
                if created:
                    print(f"Created new SportProfile for {sport_name} and {request.user.username}")
                profile.sports.add(sport_profile)
                print(f"Added {sport_name} to {request.user.username}")
            except Sport.DoesNotExist:
                # Handle the case where the sport does not exist (e.g., log error or skip)
                print(f"Sport {sport_name} does not exist")
                continue

        profile.save()

        # Handle PayPal form setup if the user chooses a role that requires payment
       


        # Handle first login redirect
        if profile.first_login:
            profile.first_login = False
            profile.save()
            return redirect('profile')
        
        return redirect('home')
    paypal_dict = {
                'business': settings.PAYPAL_RECEIVER_EMAIL,
                'amount': '149.99',
                'item_name': 'Scout Role Subscription',
                'invoice': f"subscription-{request.user.id}-{uuid.uuid4().hex}",
                'currency_code': 'PHP',
                'notify_url': request.build_absolute_uri(reverse('paypal-ipn')),
                'return_url': request.build_absolute_uri(reverse('payment-success-sub', kwargs={'profile_id': profile.id})),
                'cancel_return': request.build_absolute_uri(reverse('payment-cancelled-sub')),
            }

    # Create the PayPal form
    paypal_form = PayPalPaymentsForm(initial=paypal_dict)

    context = {
        'sports': sports,
        'paypal_form': paypal_form,  # Include the PayPal form in the context
    }

    return render(request, 'users/choose_role.html', context)


@login_required
def payment_success_sub(request, profile_id):
    # Fetch the Profile using the passed profile_id
    profile = Profile.objects.get(id=profile_id)
    print("paymanet sub profile")
    # Handle profile updates (first_login, is_scout, etc.)
    profile.first_login = False
    profile.is_scout = True
    profile.role = 'Scout'
    profile.save()

    # Redirect to the profile or home page
    return redirect('profile')  # Adjust this to your desired redirect destination




def payment_cancelled_sub(request):
    messages.warning(request, "Payment was cancelled.")
    return redirect('choose-role')  # Same as above










# Forgot password view with email sending integrated
def forgot_password(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')

        # Check if the username exists
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.error(request, "Username does not exist.")
            return render(request, 'users/forgot_password.html')

        # Check if the username has the provided email
        if user.email != email:
            messages.error(request, "The email does not match the username.")
            return render(request, 'users/forgot_password.html')

        # Generate a random password
        new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        user.set_password(new_password)
        user.save()

        # Send the new password via email
        subject = "Your LigaMeet Password Reset"
        body = f"Hi {user.username},\n\nYour new password is: {new_password}\n\nPlease log in and change it immediately."
        smtp_user = os.getenv('SMTP_USER')  
        smtp_password = os.getenv('SMTP_PASSWORD') 

        try:
            msg = EmailMessage()
            msg.set_content(body)
            msg['subject'] = subject
            msg['to'] = email
            msg['from'] = smtp_user

            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
            server.quit()

            messages.success(request, "A new password has been sent to your email.")
        except Exception as e:
            print(f"Error sending email: {e}")
            messages.error(request, "Failed to send email. Please try again later.")

        return render(request, 'users/forgot_password.html')

    return render(request, 'users/forgot_password.html')



@login_required
def reset_password_view(request):
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if new_password == confirm_password:
            user = request.user
            user.set_password(new_password)
            user.save()
            update_session_auth_hash(request, user)  # Keep the user logged in after password change
            messages.success(request, 'Your password has been updated successfully!')
            return redirect('profile')  # Redirect to the profile page
        else:
            messages.error(request, 'Passwords do not match.')
            # Redirect to the same profile page with the reset password tab active
            return redirect('profile')  # Use a URL name that points to your profile page
    else:
        # No need to render a separate template since everything is in profile.html
        return redirect('profile')  # Redirect to the profile page
