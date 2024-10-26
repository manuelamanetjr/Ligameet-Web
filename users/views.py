from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm, PlayerForm, VolleyBallForm, BasketBallForm, PhysicalInformation
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

    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=user_profile)
        player_form = PlayerForm(request.POST, instance=request.user)
        basketball_form = BasketBallForm(request.POST, instance=request.user)
        volleyball_form = VolleyBallForm(request.POST, instance=request.user)
        physical_form = PhysicalInformation(request.POST, instance=request.user)
        
        if u_form.is_valid() and p_form.is_valid() and player_form.is_valid() and basketball_form.is_valid() and volleyball_form.is_valid() and physical_form.is_valid():
            u_form.save()
            p_form.save()
            player_form.save()
            basketball_form.save()
            volleyball_form.save()
            physical_form.save()
            messages.success(request, f'Your account has been updated!')
            return redirect('profile')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=user_profile)
        player_form = PlayerForm(instance=request.user)
        basketball_form = BasketBallForm(instance=request.user)
        volleyball_form = VolleyBallForm(instance=request.user)
        physical_form = PhysicalInformation(instance=request.user)
    
    context = {
        'u_form': u_form,
        'p_form': p_form,
        'player_form': player_form,
        'basketball_form': basketball_form,
        'volleyball_form': volleyball_form,
        'physical_form': physical_form,
        'user_profile': user_profile,
        'has_basketball': has_basketball,  # Pass boolean flags to the template
        'has_volleyball': has_volleyball,  # Pass boolean flags to the template
    }
    return render(request, 'users/profile.html', context)



def choose_role(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        role = request.POST.get('role')
        sports = request.POST.get('sports').split(',')
        
        profile.role = role
        profile.sports.clear()
        for sport_name in sports:
            sport = Sport.objects.get(SPORT_NAME__iexact=sport_name)
            sport_profile = SportProfile.objects.get_or_create(USER_ID=request.user, SPORT_ID=sport)[0]
            profile.sports.add(sport_profile)
        profile.save()

        if profile.first_login:
            profile.first_login = False
            profile.save()
            return redirect('profile')
        return redirect('home')
    return render(request, 'users/choose_role.html')

