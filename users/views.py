import os
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm, PlayerForm, VolleyBallForm, BasketBallForm
from .models import Profile, SportProfile
from ligameet.models import Sport
from .forms import RoleSelectionForm
from django.contrib.auth.models import User
from django.contrib.auth.views import redirect_to_login
import requests
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import check_password
from .models import User
import random
import string
import smtplib
from email.message import EmailMessage

@csrf_exempt
def register_user(request):
    if request.method == 'POST':
        body = json.loads(request.body)
        email = body.get('email')
        username = body.get('username')
        password = body.get('password')

        # Hash password using Django's function
        from django.contrib.auth.hashers import make_password
        hashed_password = make_password(password)

        # Save the user to auth_user with hashed password
        from .models import User
        User.objects.create(
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
        return JsonResponse({'message': 'User registered successfully in Django'})

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
        
        if check_password(password, user.password):
            print("Password check successful")
            return JsonResponse({'message': 'User logged in successfully'})
        else:
            print("Password check failed")
            return JsonResponse({'error': 'Invalid login credentials'}, status=400)
    return JsonResponse({'error': 'Invalid request method'}, status=400)



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

        # Handle first login redirect
        if profile.first_login:
            profile.first_login = False
            profile.save()
            return redirect('profile')
        
        return redirect('home')

    # Pass the list of sports to the template
    return render(request, 'users/choose_role.html', {'sports': sports})

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



