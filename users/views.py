from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm, PlayerForm, VolleyBallForm, BasketBallForm, PhysicalInformation
from .models import Profile, SportProfile
from ligameet.models import Sport
from .forms import RoleSelectionForm

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

