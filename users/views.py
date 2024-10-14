from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm, PlayerForm, VolleyBallForm, BasketBallForm
from .models import Profile
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

@login_required #decorator
def profile(request):
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)
        player_form = PlayerForm(request.POST, instance=request.user)
        basketball_form = BasketBallForm(request.POST, instance=request.user)
        volleyball_form = VolleyBallForm(request.POST, instance=request.user)

        if u_form.is_valid() and p_form.is_valid() :
            u_form.save()
            p_form.save()
            player_form.save()
            basketball_form.save()
            volleyball_form.save()
            messages.success(request, f'Your account has been updated!')
            return redirect('profile')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)
        player_form = PlayerForm(instance=request.user)
        basketball_form = BasketBallForm(instance=request.user)
        volleyball_form = VolleyBallForm(instance=request.user)

    context = {
        'u_form':u_form,
        'p_form':p_form,
        'player_form':player_form,
        'basketball_form':basketball_form,
        'volleyball_form':volleyball_form
    }

    return render(request, 'users/profile.html', context)

@login_required
def choose_role(request):
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = RoleSelectionForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            if profile.first_login:  # Check after form submission
                profile.first_login = False  # Mark first login as complete
                profile.save()
                return redirect('profile')  # Redirect to profile after first login
            return redirect('home')  # Redirect to home after several logins
    else:
        form = RoleSelectionForm(instance=profile)

    return render(request, 'users/choose_role.html', {'form': form})

