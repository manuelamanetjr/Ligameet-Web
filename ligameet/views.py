import base64
from decimal import Decimal
from django.utils.timezone import now
from django.core.paginator import Paginator
import traceback
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
# from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseNotAllowed, JsonResponse, Http404
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
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.db import IntegrityError
from chat.models import *
from django.db.models import Sum, Q
from .forms import *
from django.forms import modelformset_factory
from django.conf import settings
from paypal.standard.forms import PayPalPaymentsForm
from django.urls import reverse

@login_required
def home(request):
    # Determine user's role and sports
    user_role = request.user.profile.role
    user_sports = None

    if user_role in ['Event Organizer', 'Scout']:
        # Show all events for Event Organizer and Scout
        events = Event.objects.filter(IS_POSTED=True).exclude(EVENT_STATUS='cancelled').order_by('-EVENT_DATE_START')
    else:
        # Filter events by user's sports for Coach and Player
        user_sports = SportProfile.objects.filter(USER_ID=request.user).values_list('SPORT_ID', flat=True)
        events = Event.objects.filter(
            SPORT__id__in=user_sports,
            IS_POSTED=True
        ).exclude(EVENT_STATUS='cancelled').order_by('-EVENT_DATE_START')

    # Ensure events are unique
    events = events.distinct()

    # Check for unread messages
    has_unread_messages = GroupMessage.objects.filter(
        group__members=request.user,
        is_read=False
    ).exists()

    # Implement pagination
    paginator = Paginator(events, 6)  # Show 6 events per page
    page_number = request.GET.get('page')  # Get the current page number
    page_obj = paginator.get_page(page_number)  # Get paginated events

    # Prepare context for the template
    context = {
        'page_obj': page_obj,  # Use the paginated events in the template
        'has_unread_messages': has_unread_messages,
        'user_sports': None if user_role in ['Event Organizer', 'Scout'] else list(user_sports),
    }
    return render(request, 'ligameet/home.html', context)




def about(request):
    return render(request, 'ligameet/about.html', {'title':'About'})

def landingpage(request):
    return render (request, 'ligameet/landingpage.html', {'title': 'Landing Page'})

@login_required
def create_event(request):
    if request.method == 'POST':
        # Extracting the data from the request
        event_name = request.POST.get('EVENT_NAME')
        event_date_start = parse_datetime(request.POST.get('EVENT_DATE_START'))
        event_date_end = parse_datetime(request.POST.get('EVENT_DATE_END'))
        registration_deadline = parse_datetime(request.POST.get('REGISTRATION_DEADLINE'))  # Parse datetime
        event_location = request.POST.get('EVENT_LOCATION')
        selected_sports = request.POST.getlist('SPORT')
        event_image = request.FILES.get('EVENT_IMAGE')
        contact_person = request.POST.get('CONTACT_PERSON')
        contact_phone = request.POST.get('CONTACT_PHONE')

        # Check for duplicate event name
        if Event.objects.filter(EVENT_NAME=event_name).exists():
            return JsonResponse({'success': False, 'error': 'An event with this name already exists.'})

        # Check for overlapping events at the same location
        overlapping_event = Event.objects.filter(
            EVENT_LOCATION=event_location,
            EVENT_DATE_END__gt=event_date_start,
            EVENT_DATE_START__lt=event_date_end
        ).exists()
        if overlapping_event:
            return JsonResponse({'success': False, 'error': 'An event is already scheduled at this location during the selected time range. Please choose a different time.'})

        # Create the event instance
        event = Event(
            EVENT_NAME=event_name,
            EVENT_DATE_START=event_date_start,
            EVENT_DATE_END=event_date_end,
            REGISTRATION_DEADLINE=registration_deadline,  # Save the deadline
            EVENT_LOCATION=event_location,
            EVENT_ORGANIZER=request.user,
            EVENT_IMAGE=event_image,
            CONTACT_PERSON=contact_person,
            CONTACT_PHONE=contact_phone,
            EVENT_STATUS = 'draft'
        )

        # Save the event first to get an ID
        event.save()

        # Associate selected sports with the event
        for sport_id in selected_sports:
            try:
                sport = Sport.objects.get(id=int(sport_id))
                event.SPORT.add(sport)

                # # Save sport details and categories (if needed)
                # sport_requirement = SportDetails(event=event, sport=sport)
                # sport_requirement.save()

            except ValueError:
                print(f"Invalid sport ID: {sport_id}")
                continue
            except Sport.DoesNotExist:
                print(f"Sport with ID {sport_id} does not exist.")
                continue
        messages.success(request, f'Event {event_name} Created Successfully')
        return JsonResponse({'success': True, 'event_id': event.id})

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

@login_required
def event_dashboard(request): # TODO paginate
    try:
        profile = request.user.profile
        if profile.role == 'Event Organizer':
            # Fetch all events created by the logged-in user (event organizer)
            organizer_events = Event.objects.filter(EVENT_ORGANIZER=request.user).order_by('-EVENT_DATE_START')

            # Fetch sports for the filtering dropdown
            sports = Sport.objects.all()

            has_unread_messages = GroupMessage.objects.filter(
                group__members=request.user,
                is_read=False
            ).exists()
            notifications = Notification.objects.filter(user=request.user).order_by('-created_at')

            context = {
                'organizer_events': organizer_events,
                'sports': sports,
                'has_unread_messages': has_unread_messages,
                'notifications': notifications,
            }
            return render(request, 'ligameet/events_dashboard.html', context)
        else:
            return redirect('home')

    except Profile.DoesNotExist:
        return redirect('home')
    
    
@login_required
def event_mark_notification_read(request):
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
def event_details(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    event.update_status()  # Ensure the event's status is updated
    sports_with_details = []

    user_role = request.user.profile.role  # Assuming `profile.role` stores the user's role

    has_unread_messages = GroupMessage.objects.filter(
        group__members=request.user,
        is_read=False
    ).exists()

    # Determine which sports to show based on user role
    if user_role in ['Event Organizer', 'Scout']:
        # Show all sports for Event Organizer and Scout
        event_sports = event.SPORT.all()
    else:
        # Filter sports for Coaches and Players based on their associated sports
        user_sports = request.user.sportprofile_set.values_list('SPORT_ID', flat=True)
        event_sports = event.SPORT.filter(id__in=user_sports)

    # Loop through each sport associated with the event
    for sport in event_sports:
        # Filter categories linked to the current event
        sport_categories = TeamCategory.objects.filter(sport=sport, event=event).prefetch_related('sport_details')

        categories_with_forms = []
        for category in sport_categories:
            sport_details = category.sport_details.first()  # Assuming one-to-one relationship with SportDetails
            
            # Check if the coach has already registered for this category (paid invoice)
            invoice = Invoice.objects.filter(
                team_category=category,
                coach=request.user,
                is_paid=True
            ).first()  # Get the first paid invoice for this category and coach
            
            if invoice:
                # If there's a paid invoice, mark as registered
                categories_with_forms.append({
                    'category': category,
                    'paypal_form': None,
                    'sport_details': sport_details,
                    'is_registered': True,
                })
            else:
                # Otherwise, prepare the PayPal form
                if sport_details:
                    paypal_dict = {
                        'business': settings.PAYPAL_RECEIVER_EMAIL,
                        'amount': sport_details.entrance_fee,  # Use entrance fee from SportDetails
                        'item_name': f'Registration for {category.name} - {sport.SPORT_NAME} ({event.EVENT_NAME})',
                        'invoice': f"{event.id}-{category.id}",
                        'currency_code': 'PHP',
                        'notify_url': request.build_absolute_uri(reverse('paypal-ipn')),
                        'return_url': request.build_absolute_uri(reverse('payment-success', args=[event.id, category.id])),
                        'cancel_return': request.build_absolute_uri(reverse('payment-cancelled', args=[event_id])),
                    }

                    # Initialize PayPal form
                    form = PayPalPaymentsForm(initial=paypal_dict)

                    categories_with_forms.append({
                        'category': category,
                        'paypal_form': form,
                        'sport_details': sport_details,
                        'is_registered': False,
                    })
                else:
                    categories_with_forms.append({
                        'category': category,
                        'paypal_form': None,
                        'sport_details': None,
                        'is_registered': False,
                    })

        sports_with_details.append({
            'sport': sport,
            'categories': categories_with_forms,
        })

    context = {
        'event': event,
        'sports_with_details': sports_with_details,
        'has_unread_messages': has_unread_messages,
    }

    return render(request, 'ligameet/event_details.html', context)



@login_required
def edit_sport_details(request, event_id, sport_id):
    event = get_object_or_404(Event, id=event_id)
    sport = get_object_or_404(Sport, id=sport_id)
    
    if request.method == 'POST':
        # Check if we're processing category deletion
        if 'delete_category' in request.POST:
            category_id = request.POST.get('category_id')
            category = get_object_or_404(TeamCategory, id=category_id)
            category.delete()
            messages.success(request, 'Category was successfully removed.')
            return redirect('edit-sport-details', event_id=event.id, sport_id=sport.id)

        # Process the form data for editing categories
        category_ids = request.POST.getlist('category_ids[]')
        category_names = request.POST.getlist('category_names[]')
        number_of_teams = request.POST.getlist('number_of_teams[]')
        players_per_team = request.POST.getlist('players_per_team[]')
        entrance_fees = request.POST.getlist('entrance_fees[]')

        # Update or create categories and sport details
        for i in range(len(category_names)):
            if category_ids[i]:
                category = TeamCategory.objects.get(id=category_ids[i])
            else:
                category = TeamCategory(sport=sport, event=event)
            
            category.name = category_names[i]
            category.save()
            
            # Ensure number_of_teams, players_per_team, and entrance_fees are not empty
            number_of_teams_value = number_of_teams[i] if number_of_teams[i] else 0
            players_per_team_value = players_per_team[i] if players_per_team[i] else 0
            entrance_fee_value = entrance_fees[i] if entrance_fees[i] else 0.00
            
            # Create or update sport details
            sport_details, created = SportDetails.objects.get_or_create(team_category=category)
            sport_details.number_of_teams = int(number_of_teams_value)  # Convert to integer
            sport_details.players_per_team = int(players_per_team_value)  # Convert to integer
            sport_details.entrance_fee = float(entrance_fee_value)  # Convert to float
            sport_details.save()

        messages.success(request, f'Edited {event.EVENT_NAME} Sports successfully!')    
        return redirect('edit-sport-details', event_id=event.id, sport_id=sport.id)
    
    # For GET requests, load existing categories
    sport_categories = TeamCategory.objects.filter(sport=sport, event=event).prefetch_related('sport_details')
    
    context = {
        'event': event,
        'sport': sport,
        'sport_categories': sport_categories,
    }
    
    return render(request, 'ligameet/edit_sport_details.html', context)


@login_required
def delete_category(request, category_id):
    if request.method == 'POST':
        # Get event_id and sport_id from the form
        event_id = request.POST.get('event_id')
        sport_id = request.POST.get('sport_id')

        # Fetch the category to be deleted
        category = get_object_or_404(TeamCategory, id=category_id)

        # Ensure that the category exists
        if category:
            category.delete()
            # Add a success message
            messages.success(request, 'Category was successfully removed.')
        else:
            # Handle case if category is not found
            messages.error(request, 'Category not found.')

        # Redirect to the edit-sport-details page with the event_id and sport_id
        return redirect('edit-sport-details', event_id=event_id, sport_id=sport_id)
    else:
        # If not a POST request, raise an error
        raise Http404("Invalid request method")


@login_required
def post_event(request, event_id):
    if request.method == 'POST':
        event = get_object_or_404(Event, id=event_id)
        if request.user == event.EVENT_ORGANIZER:
            event.IS_POSTED = 'True'  # Update with your status field
            event.EVENT_STATUS = "open"
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

            # Find all the invoices linked to this event's categories
            invoices = Invoice.objects.filter(team_category__event=event, is_paid=True)

            # Create a set of unique coaches from the invoices
            coaches = invoices.values('coach').distinct()

            # Process refunds and update wallets for each invoice
            for invoice in invoices:
                # Get the coach linked to the invoice
                coach = invoice.coach

                # Find the coach's wallet or create one if it doesn't exist
                wallet, created = Wallet.objects.get_or_create(user=coach)

                # Add the refund amount to the coach's wallet balance
                wallet.WALLET_BALANCE += invoice.amount
                wallet.save()

                # Create a WalletTransaction for the refund
                WalletTransaction.objects.create(
                    wallet=wallet,
                    amount=invoice.amount,
                    transaction_type='refund',
                    description=f"Refund for {event.EVENT_NAME} - {invoice.team_category.name}",
                )

            # Send a single notification to each unique coach
            for coach_data in coaches:
                coach = coach_data['coach']
                Notification.objects.create(
                    user_id=coach,
                    sender=request.user,
                    message=f"The event '{event.EVENT_NAME}' you registered for has been cancelled. Refunds have been processed for your teams.",
                    created_at=now(),
                )

            # Add success message
            messages.success(request, 'Event cancelled, refunds processed, and notifications sent to all registered coaches!')

            # Return a JSON response with the success message
            return JsonResponse({
                'success': True,
                'message': 'Event cancelled, refunds processed, and notifications sent to all registered coaches!',
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



# TODO backed for registering team in the event
def payment_success(request, event_id, category_id):
    # Print debug output to ensure both event_id and category_id are being passed correctly
    print(f"Payment successful! Event ID: {event_id}, Category ID: {category_id}")

    messages.success(request, "Payment successful! Please select a team to register.")
    return redirect('team-selection', event_id=event_id, category_id=category_id)

def payment_cancelled(request, event_id):
    messages.warning(request, "Payment was cancelled.")
    return redirect('event-details', event_id=event_id)


@login_required
def pay_with_wallet(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        sport_id = data.get('sport_id')
        category_id = data.get('category_id')

        # Fetch the sport and category
        sport = get_object_or_404(Sport, id=sport_id)
        category = get_object_or_404(TeamCategory, id=category_id)

        # Get the entrance fee from SportDetails
        sport_detail = get_object_or_404(SportDetails, team_category=category)

        # Check if the user has a wallet and enough balance
        wallet = Wallet.objects.filter(user=request.user).first()
        if not wallet:
            return JsonResponse({'success': False, 'message': 'Wallet not found.'})

        if wallet.WALLET_BALANCE < sport_detail.entrance_fee:
            return JsonResponse({'success': False, 'message': 'Insufficient wallet balance.'})

        # Deduct the fee from the wallet balance
        wallet.WALLET_BALANCE -= sport_detail.entrance_fee
        wallet.save()

        # Add a success message
        success_message = "Registration successful. Please select your team for the event."

        return JsonResponse({
            'success': True,
            'message': success_message,  # Include the success message here
            'redirect_url': reverse('team-selection', args=[category.event.id, category.id])
        })

    return JsonResponse({'success': False, 'message': 'Invalid request method.'})


@login_required
def team_selection(request, event_id, category_id):
    event = get_object_or_404(Event, id=event_id)  # Fetch the event by ID
    category = get_object_or_404(TeamCategory, id=category_id)  # Fetch the TeamCategory by ID
    sport = category.sport  # Get the related Sport from the category

    # Get the related SportDetails for this category
    sport_details = get_object_or_404(SportDetails, team_category=category)
    required_players = sport_details.players_per_team  # Players per team for this category

    # Get all teams of the current user (coach) for this sport
    teams = Team.objects.filter(COACH_ID=request.user, SPORT_ID=sport)

    if request.method == 'POST':
        selected_team_id = request.POST.get('team')
        try:
            selected_team = teams.get(id=selected_team_id)

            # Check if the team has already been registered for this event and sport category
            if Invoice.objects.filter(
                team=selected_team,
                event=event,
                team_category=category
            ).exists():
                messages.error(
                    request,
                    f"Team {selected_team.TEAM_NAME} is already registered in this category."
                )
                return redirect('team-selection', event_id=event_id, category_id=category_id)

            # Count the participants in the selected team using TeamParticipant
            player_count = TeamParticipant.objects.filter(TEAM_ID=selected_team).count()

            # Check if the team's player count meets the required number
            if player_count < required_players:
                messages.error(
                    request,
                    f"{selected_team.TEAM_NAME} does not have enough players. Minimum required: {required_players}."
                )
                return redirect('team-selection', event_id=event_id, category_id=category_id)

            # Add the selected team to the SportDetails teams
            sport_details.teams.add(selected_team)
            sport_details.save()

            # Get the entrance fee from SportDetails
            entrance_fee = sport_details.entrance_fee

            # Create an invoice for this registration
            Invoice.objects.create(
                coach=request.user,  # The coach registering the team
                team=selected_team,
                event=event,
                team_category=category,
                amount=entrance_fee,
                is_paid=True,
            )
            event.update_status()
            messages.success(request, f"Registered {selected_team.TEAM_NAME} to {sport.SPORT_NAME} successfully!")
            return redirect('event-details', event_id=event_id)

        except Team.DoesNotExist:
            messages.error(request, "Invalid team selection.")
            return redirect('team-selection', event_id=event_id, category_id=category_id)

    return render(request, 'ligameet/team_selection.html', {
        'event': event,
        'category': category,
        'teams': teams,
        'sport': sport,
        'required_players': required_players,
    })

@login_required
def leave_game(request, sport_id, team_category_id):
    if request.method == "POST":
        # Get the Sport and TeamCategory
        sport = get_object_or_404(Sport, id=sport_id)
        team_category = get_object_or_404(TeamCategory, id=team_category_id)

        # Get the SportDetails for the specified sport and team category
        sport_details = get_object_or_404(SportDetails, team_category=team_category, teams__SPORT_ID=sport)

        # Get the team associated with the coach and sport from SportDetails
        team = sport_details.teams.filter(SPORT_ID=sport, COACH_ID=request.user).first()

        if not team:
            messages.error(request, "No team found associated with this sport and coach.")
            return redirect('home')

        # Refund logic
        entrance_fee = sport_details.entrance_fee  # Access the entrance_fee from SportDetails
        refund_amount = entrance_fee * Decimal(0.8)  # Calculate 80% refund

        # Update wallet
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        wallet.WALLET_BALANCE += refund_amount
        wallet.save()

        # Log the transaction
        WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type='refund',
            amount=refund_amount,
            description=f"Refund for leaving {sport.SPORT_NAME} ({team_category.name})."
        )

        # Remove the team from the SportDetails
        sport_details.teams.remove(team)

        # Find and update the Invoice linked to this Team and TeamCategory
        invoice = Invoice.objects.filter(
            coach=request.user,
            team=team,
            team_category=team_category,
            is_paid=True  # Ensure it matches a paid invoice
        ).first()

        if invoice:
            invoice.is_paid = False
            invoice.save()
        else:
            messages.error(request, "No matching invoice was found to update.")
        
        event = team_category.event
        # Send notification to the event organizer
        event_organizer = event.EVENT_ORGANIZER
        Notification.objects.create(
            user=event_organizer,  # Recipient is the event organizer
            sender=request.user,  # Sender is the current coach
            message=f"The team '{team.TEAM_NAME}' has left the game in {sport.SPORT_NAME} ({team_category.name}).",
            created_at=now()
        )

        messages.success(request, f"You have successfully left the game and received a refund of ₱{refund_amount}.")
        return redirect('home')  # Adjust redirection as needed

    return HttpResponseNotAllowed(['POST'])

from django.db.models import Q
@login_required
def wallet_dashboard(request):
    # Fetch the user's wallet
    wallet = get_object_or_404(Wallet, user=request.user)

    # Get invoices associated with the logged-in user (filtering invoices for the user or the coach)
    invoices = Invoice.objects.filter(
        models.Q(user=request.user) | models.Q(coach=request.user)
    ).select_related('event', 'team_category', 'team').order_by('-created_at')

    # Fetch wallet transactions for the logged-in user's wallet
    transactions = WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')

    # Paginate the invoices (limit to 10 per page)
    paginator_invoices = Paginator(invoices, 10)  # Show 10 invoices per page
    page_number_invoices = request.GET.get('page')  # Get current page number from the request
    page_obj_invoices = paginator_invoices.get_page(page_number_invoices)  # Get the page object for the current page

    # Paginate the wallet transactions (limit to 10 per page)
    paginator_transactions = Paginator(transactions, 10)  # Show 10 transactions per page
    page_number_transactions = request.GET.get('page')  # Get current page number for transactions
    page_obj_transactions = paginator_transactions.get_page(page_number_transactions)  # Get the page object for the current page

    context = {
        'wallet': wallet,
        'page_obj_invoices': page_obj_invoices,  # Pass the page object for invoices to the template
        'page_obj_transactions': page_obj_transactions,  # Pass the page object for transactions to the template
    }
    return render(request, 'ligameet/wallet_dashboard.html', context)


def get_recent_matches(sport_id=None, category_id=None, limit=5):
    try:
        # Print out raw IDs for debugging
        print(f"get_recent_matches - sport_id: {sport_id}, category_id: {category_id}")
        
        # Base query to fetch recent matches
        matches = MatchDetails.objects.select_related('team1', 'team2', 'match')
        
        # If both sport_id and category_id are provided, filter accordingly
        if sport_id and category_id:
            # First, find the relevant SportDetails
            sport_details = SportDetails.objects.filter(
                team_category__id=category_id
            )
            print("Matching SportDetails:")
            print(list(sport_details.values('id', 'team_category__name')))
            
            # Filter matches based on the sport details and team category
            matches = matches.filter(
                Q(team1__SPORT_ID_id=sport_id) & 
                Q(team2__SPORT_ID_id=sport_id)
            )
        
        # Order by most recent and limit results
        recent_matches = matches.order_by('-match__MATCH_DATE')[:limit]
        
        # Print out matching matches
        print("Matching Matches:")
        for match in recent_matches:
            print(f"Match: {match.team1.TEAM_NAME} vs {match.team2.TEAM_NAME}")
        
        return recent_matches
    
    except Exception as e:
        print(f"Error in get_recent_matches: {e}")
        import traceback
        traceback.print_exc()
        return MatchDetails.objects.none()


from django.shortcuts import redirect, render
from django.http import HttpResponse
from .models import Team, Match, TeamCategory, SportDetails, MatchDetails
from django.contrib import messages

def create_match(request, event_id=None):
    sport_id = request.GET.get('sport_id') or request.POST.get('sport_id')
    category_id = request.GET.get('category_id') or request.POST.get('category_id')
    print(f"Debug - sport_id: {sport_id}, category_id: {category_id}")
    created_match_teams = None

    if not sport_id or not category_id:
        return HttpResponse('Invalid Sport ID or Category ID', status=400)

    try:
        category = TeamCategory.objects.get(id=category_id)
    except TeamCategory.DoesNotExist:
        return HttpResponse('Invalid Category ID', status=400)

    sport_details = SportDetails.objects.filter(team_category=category).first()

    if sport_details:
        # Fetch teams that are not already part of any match in MatchDetails
        existing_match_teams = MatchDetails.objects.values_list('team1', 'team2')
        excluded_team_ids = set(team_id for pair in existing_match_teams for team_id in pair)
        teams = sport_details.teams.exclude(id__in=excluded_team_ids)
    else:
        teams = []

    if request.method == 'POST':
        team1_id = request.POST.get('team1')
        team2_id = request.POST.get('team2')
        match_date = request.POST.get('match_date')

        if not team1_id or not team2_id or not match_date:
            return HttpResponse('Missing team selection or match date', status=400)

        try:
            team1 = Team.objects.get(id=team1_id)
            team2 = Team.objects.get(id=team2_id)

            # Create a single Match instance without using TEAM_ID
            match = Match.objects.create(MATCH_DATE=match_date, MATCH_TYPE='some_type', MATCH_CATEGORY='some_category', MATCH_STATUS='upcoming')
            match_details = MatchDetails.objects.create(match=match, team1=team1, team2=team2, match_date=match_date)

            created_match_teams = (team1, team2)

            messages.success(request, 'Match has been successfully added')

            # Redirect with match details to ensure the variable is retained
            return redirect(request.path + f'?sport_id={sport_id}&category_id={category_id}&event_id={event_id}&match_teams={team1_id},{team2_id}')

        except Team.DoesNotExist:
            return HttpResponse('One or both of the selected teams do not exist', status=400)
        

    match_teams = request.GET.get('match_teams')
    if match_teams:
        team1_id, team2_id = match_teams.split(',')
        try:
            team1 = Team.objects.get(id=team1_id)
            team2 = Team.objects.get(id=team2_id)
            created_match_teams = (team1, team2)
        except Team.DoesNotExist:
            created_match_teams = None
            
    recent_matches = get_recent_matches(sport_id, category_id)

    return render(request, 'ligameet/matchmaking.html', {
        'teams': teams,
        'team_category': category,
        'event_id': event_id,
        'sport_id': sport_id,
        'category_id': category_id,
        'created_match_teams': created_match_teams,
        'recent_matches': recent_matches
    })
    





@login_required
def player_dashboard(request):
    try:
        profile = request.user.profile
        if profile.role == 'Player':
            chat_groups = ChatGroup.objects.all()
            
            sport_profiles = SportProfile.objects.filter(USER_ID=request.user)
            selected_sports = [sp.SPORT_ID.id for sp in sport_profiles]

            query = request.GET.get('q', '')
            match_type = request.GET.get('type', '')
            match_category = request.GET.get('category', '')
            invitations = Invitation.objects.filter(user=request.user, status='Pending')
            participant = User.objects.filter(id=request.user.id).first()
            recent_activities = Activity.objects.filter(user=request.user).order_by('-timestamp')[:5]
            notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
            unread_notifications_count = notifications.filter(is_read=False).count()

            my_teams = Team.objects.filter(teamparticipant__USER_ID=request.user).prefetch_related(
                Prefetch('teamparticipant_set', queryset=TeamParticipant.objects.select_related('USER_ID'))
            )
            
            my_teams_and_participants = [
                {
                    'team': team,
                    'participants': TeamParticipant.objects.filter(TEAM_ID=team).select_related('USER_ID')
                }
                for team in my_teams
            ]

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
                'my_teams_and_participants': my_teams_and_participants,
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
        if profile.role != 'Scout':
            return redirect('home')

        players = User.objects.filter(profile__role='Player')
        filter_form = ScoutPlayerFilterForm(request.GET)
        search_query = request.GET.get('search', '').strip()
        position_filters = request.GET.getlist('position')
        selected_sport_id = request.GET.get('sport_id', '')

        if selected_sport_id:
            players = players.filter(sportprofile__SPORT_ID__id=selected_sport_id)

        if search_query:
            players = players.filter(
                Q(username__icontains=search_query) |
                Q(profile__FIRST_NAME__icontains=search_query) |
                Q(profile__LAST_NAME__icontains=search_query)
            )

        sport_position_map = {
            '1': 'basketball_position_played',
            '2': 'volleyball_position_played',
        }

        if position_filters and selected_sport_id in sport_position_map:
            position_field = sport_position_map[selected_sport_id]
            players = players.filter(
                **{f"profile__{position_field}__in": position_filters}
            )

        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
        unread_notifications_count = notifications.filter(is_read=False).count()

        recruited_players = User.objects.filter(recruited_by__scout=request.user, recruited_by__is_recruited=True)
        recruited_player_ids = recruited_players.values_list('id', flat=True)

        sports = Sport.objects.all()

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
        }

        return render(request, 'ligameet/scout_dashboard.html', {
            'title': 'Scout Dashboard',
            'players': players,
            'filter_form': filter_form,
            'sports': sports,
            'sport_positions': json.dumps(sport_positions),
            'selected_sport_id': selected_sport_id,
            'selected_positions': json.dumps(position_filters),
            'notifications': notifications,
            'unread_notifications_count': unread_notifications_count,
            'recruited_players': recruited_players,
            'recruited_player_ids': recruited_player_ids,
        })
    except Profile.DoesNotExist:
        return redirect('home')





    
    
@csrf_exempt
@require_POST
def recruit_player(request, player_id):
    scout = request.user
    player = User.objects.get(id=player_id)
    data = json.loads(request.body)
    is_recruited = data['is_recruited']

    recruitment, created = PlayerRecruitment.objects.get_or_create(scout=scout, player=player)
    recruitment.is_recruited = is_recruited
    recruitment.save()

    return JsonResponse({'status': 'success'})



@login_required
def get_recruited_players(request):
    recruited_players = User.objects.filter(recruited_by__scout=request.user, recruited_by__is_recruited=True)
    recruited_players_data = [{
        'id': player.id,
        'username': player.username,
        'profile': {
            'position': player.profile.position,
            'FIRST_NAME': player.profile.FIRST_NAME,
            'LAST_NAME': player.profile.LAST_NAME,
            'PHONE': player.profile.PHONE,
        },
        'rating': player.profile.rating,
        'matches_played': player.profile.matches_played,
        'wins': player.profile.wins,
        'mvp_awards': player.profile.mvp_awards,
    } for player in recruited_players]

    return JsonResponse({'recruited_players': recruited_players_data})





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
            position_field = 'profile__basketball_position_played' if sport_name == 'basketball' else 'profile__volleyball_position_played'   
            
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


def bracketing_dashboard(request):
    return render(request, 'ligameet/bracket.html')








    
