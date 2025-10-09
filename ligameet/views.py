import base64
from decimal import Decimal
from django.utils.timezone import now
from django.core.paginator import Paginator
import uuid
import traceback
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
# from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse, Http404
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

    for event in events:
        event.update_status()

    events = events.distinct() # Ensure events are unique

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
def event_dashboard(request): 
    try:
        profile = request.user.profile
        if profile.role == 'Event Organizer':
            # Fetch all events created by the logged-in user (event organizer)
            organizer_events = Event.objects.filter(EVENT_ORGANIZER=request.user).order_by('-EVENT_DATE_START')
            
            for event in organizer_events: #update status
                event.update_status()

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
    
    
    
def event_notifications_view(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    unread_notifications_count = notifications.filter(is_read=False).count()
    return render(request, 'ligameet/event_dashboard.html', {
        'notifications': notifications,
        'unread_notifications_count': unread_notifications_count,
    })


from django.http import JsonResponse

@login_required
@require_POST
def event_mark_notification_read(request):
    try:
        data = json.loads(request.body)
        notification_id = data.get('notification_id')
        notification = Notification.objects.get(id=notification_id, user=request.user)

        # Mark the notification as read
        notification.is_read = True
        notification.save()

        # Get updated unread notifications count for the user
        unread_notifications_count = Notification.objects.filter(user=request.user, is_read=False).count()

        # Send response with the updated unread count
        return JsonResponse({
            'message': 'Notification marked as read',
            'unread_notifications_count': unread_notifications_count
        })
    except Notification.DoesNotExist:
        return JsonResponse({'message': 'Notification not found'}, status=404)
    except Exception as e:
        print(f"Error: {str(e)}")  # Logging the error
        return JsonResponse({'message': f'Error: {str(e)}'}, status=500)








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
            
            # Calculate remaining slots
            if sport_details:
                remaining_slots = max(0, sport_details.number_of_teams - sport_details.teams.count())
            else:
                remaining_slots = 0
            
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
                    'remaining_slots': remaining_slots,
                    'is_registered': True,
                })
            else:
                # Otherwise, prepare the PayPal form
                if sport_details and remaining_slots > 0:
                    paypal_dict = {
                        'business': settings.PAYPAL_RECEIVER_EMAIL,
                        'amount': sport_details.entrance_fee,  # Use entrance fee from SportDetails
                        'item_name': f'Registration for {category.name} - {sport.SPORT_NAME} ({event.EVENT_NAME})',
                         'invoice': f"{event.id}-{category.id}-{uuid.uuid4().hex}",
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
                        'remaining_slots': remaining_slots,
                        'is_registered': False,
                    })
                else:
                    categories_with_forms.append({
                        'category': category,
                        'paypal_form': None,
                        'sport_details': sport_details,
                        'remaining_slots': remaining_slots,
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
        # Handle form data for editing categories
        category_ids = request.POST.getlist('category_ids[]')
        category_names = request.POST.getlist('category_names[]')
        number_of_teams = request.POST.getlist('number_of_teams[]')
        players_per_team = request.POST.getlist('players_per_team[]')
        entrance_fees = request.POST.getlist('entrance_fees[]')
        elimination_types = request.POST.getlist('elimination_types[]')  # New field

        for i in range(len(category_names)):
            if category_ids[i]:
                category = TeamCategory.objects.get(id=category_ids[i])
            else:
                category = TeamCategory(sport=sport, event=event)

            category.name = category_names[i]
            category.save()

            # Ensure fields are not empty
            number_of_teams_value = number_of_teams[i] if number_of_teams[i] else 0
            players_per_team_value = players_per_team[i] if players_per_team[i] else 0
            entrance_fee_value = entrance_fees[i] if entrance_fees[i] else 0.00
            elimination_type_value = elimination_types[i] if elimination_types[i] else 'SINGLE'

            # Create or update sport details
            sport_details, created = SportDetails.objects.get_or_create(team_category=category)
            sport_details.number_of_teams = int(number_of_teams_value)
            sport_details.players_per_team = int(players_per_team_value)
            sport_details.entrance_fee = float(entrance_fee_value)
            sport_details.elimination_type = elimination_type_value  # Save elimination type
            sport_details.save()

        messages.success(request, f'Edited {event.EVENT_NAME} Sports successfully!')    
        return redirect('edit-sport-details', event_id=event.id, sport_id=sport.id)
    
    if request.method == 'POST' and 'delete_category' in request.POST:
        category_id = request.POST.get('category_id')
        # Retrieve the category and delete it
        category = get_object_or_404(TeamCategory, id=category_id)
        category.delete()

        # Optionally, add a success message
        messages.success(request, "Category removed successfully.")
        return redirect('edit-sport-details', event_id=event_id, sport_id=sport_id)
    
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
                    description=f"Event cancelled. Refund for Event:{event.EVENT_NAME} - {invoice.team_category.name}",
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

        # Get the entrance fee and number of teams limit from SportDetails
        sport_detail = get_object_or_404(SportDetails, team_category=category)

        # Check if the user has a wallet and enough balance
        wallet = Wallet.objects.filter(user=request.user).first()
        if not wallet:
            return JsonResponse({'success': False, 'message': 'Wallet not found.'})

        if wallet.WALLET_BALANCE < sport_detail.entrance_fee:
            return JsonResponse({'success': False, 'message': 'Insufficient wallet balance.'})

        # Get all the coach's teams for the specific sport
        coach_teams = Team.objects.filter(COACH_ID=request.user, SPORT_ID=sport)  # Teams linked to this coach for the specific sport

        # Check if at least one of the coach's teams has enough players
        valid_team_found = False
        for team in coach_teams:
            # Count the number of players in the team
            num_players = TeamParticipant.objects.filter(TEAM_ID=team).count()

            # If at least one team has enough players, allow the payment
            if num_players >= sport_detail.number_of_teams:
                valid_team_found = True
                break  # No need to check further teams, as one valid team is found

        if not valid_team_found:
            return JsonResponse({
                'success': False,
                'message': f"None of your teams meet the required number of players for the sport category {category.name}. You need at least {sport_detail.number_of_teams} players."
            })

        # If a valid team is found, proceed with the wallet payment
        wallet.WALLET_BALANCE -= sport_detail.entrance_fee
        wallet.save()

        # Success message and redirect URL
        success_message = "Registration successful. Please select your team for the event."

        return JsonResponse({
            'success': True,
            'message': success_message,
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

            # Check if the selected team's type matches the team category
            # if selected_team.TEAM_TYPE != category.name:
            #     messages.error(
            #         request,
            #         f"Team {selected_team.TEAM_NAME} does not match the team category {category.name}. Please select a team that matches this category."
            #     )
            #     return redirect('team-selection', event_id=event_id, category_id=category_id)

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

            # Send a notification to the event organizer
            Notification.objects.create(
                user=event.EVENT_ORGANIZER,  # Event organizer
                sender=request.user,  # The coach who registered the team
                message=f"Team {selected_team.TEAM_NAME} has been registered in the {category.name} category for the {sport.SPORT_NAME} sport in your event {event.EVENT_NAME}.",
            )

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
        sport_details_qs = SportDetails.objects.filter(team_category=team_category, teams__SPORT_ID=sport)
        sport_details = sport_details_qs.first()

        if not sport_details:
            messages.error(request, "Sport details not found for the given sport and team category.")
            return redirect('home')

        if sport_details_qs.count() > 1:
            # Log duplicates for debugging
            print("Duplicate SportDetails found:", sport_details_qs)

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
            description=f"Refund for leaving {sport.SPORT_NAME} ({team_category.name}) in the event '{team_category.event.EVENT_NAME}'."
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
        
        # Send notification to the event organizer
        event = team_category.event
        event_organizer = event.EVENT_ORGANIZER
        Notification.objects.create(
            user=event_organizer,  # Recipient is the event organizer
            sender=request.user,  # Sender is the current coach
            message=f"The team '{team.TEAM_NAME}' has left the game in {sport.SPORT_NAME} ({team_category.name}).",
            created_at=now()
        )

        messages.success(request, f"You have successfully left the game and received a refund of ₱{refund_amount:.2f}.")
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





@login_required
def create_match(request, sport_details_id):
    from django.utils.safestring import mark_safe
    import json

    sport_details = get_object_or_404(SportDetails, id=sport_details_id)
    sport = sport_details.team_category.sport  # Retrieve the sport associated with the SportDetails

    if request.method == 'POST':
        # Get data from the form
        round = request.POST.get('round')
        bracket = request.POST.get('bracket')
        team_a_id = request.POST.get('teamA')
        team_b_id = request.POST.get('teamB')
        date_time = request.POST.get('dateTime')

        # Retrieve the Team instances using the provided IDs
        team_a = Team.objects.get(id=team_a_id)
        team_b = Team.objects.get(id=team_b_id)

        # Check if a match already exists with the same schedule in the same sport_details
        if Match.objects.filter(sport_details=sport_details, schedule=date_time).exists():
            messages.error(request, f"A match is already scheduled at this time.")
            return redirect('get_bracket_data', sport_details_id=sport_details.id)

        # Add team names to the bracket if conditions are met
        if round.lower() == "first round" and bracket.lower() == "upper bracket":
            bracket_data = BracketData.objects.filter(sport_details=sport_details).first()
            if bracket_data:
                # Ensure bracket_data.teams is a JSON string before loading
                if isinstance(bracket_data.teams, str):
                    bracket_teams = json.loads(bracket_data.teams)
                elif isinstance(bracket_data.teams, list):
                    bracket_teams = bracket_data.teams
                else:
                    messages.error(request, "Invalid bracket data format.")
                    return redirect('get_bracket_data', sport_details_id=sport_details.id)

                # Check if either team already exists in the bracket
                for pair in bracket_teams:
                    if team_a.TEAM_NAME in pair or team_b.TEAM_NAME in pair:
                        messages.error(request, f"One or both teams are already in the bracket.")
                        return redirect('get_bracket_data', sport_details_id=sport_details.id)

                # Find the first available slot where both teams are None
                for i, pair in enumerate(bracket_teams):
                    if pair[0] is None and pair[1] is None:
                        # Add the team names
                        bracket_teams[i] = [team_a.TEAM_NAME, team_b.TEAM_NAME]
                        break

                # Update the bracket data in the database
                bracket_data.teams = json.dumps(bracket_teams)  # Save as JSON string
                bracket_data.save()

        # Limit matches creation based on the number of teams in the first round
        if round.lower() == "first round":
            team_count = sport_details.teams.count()  # Count the number of teams linked to the sport details
            max_matches = team_count // 2  # Calculate the maximum number of matches allowed for the first round

            # Check the number of matches already created for the first round
            first_round_matches = Match.objects.filter(sport_details=sport_details, round="First Round").count()

            if first_round_matches >= max_matches:
                messages.error(
                    request,
                    f"Cannot create more matches for the first round. Maximum allowed matches ({max_matches}) reached."
                )
                return redirect('get_bracket_data', sport_details_id=sport_details.id)

        # Create a new match
        match = Match(
            round=round,
            bracket=bracket,
            team_a=team_a,
            team_b=team_b,
            schedule=date_time,
            sport_details=sport_details
        )
        match.save()

        # Retrieve players for both teams
        team_a_players = TeamParticipant.objects.filter(TEAM_ID=team_a).select_related('USER_ID')
        team_b_players = TeamParticipant.objects.filter(TEAM_ID=team_b).select_related('USER_ID')

        # Create PlayerStats for Team A players
        for participant in team_a_players:
            player_stats = PlayerStats.objects.create(
                match=match,
                player=participant.USER_ID,
                team=team_a,
                sport=sport
            )
            # Create sport-specific stats
            if sport.SPORT_NAME.lower() == "basketball":
                BasketballStats.objects.create(player_stats=player_stats)
            elif sport.SPORT_NAME.lower() == "volleyball":
                VolleyballStats.objects.create(player_stats=player_stats)

        # Create PlayerStats for Team B players
        for participant in team_b_players:
            player_stats = PlayerStats.objects.create(
                match=match,
                player=participant.USER_ID,
                team=team_b,
                sport=sport
            )
            # Create sport-specific stats
            if sport.SPORT_NAME.lower() == "basketball":
                BasketballStats.objects.create(player_stats=player_stats)
            elif sport.SPORT_NAME.lower() == "volleyball":
                VolleyballStats.objects.create(player_stats=player_stats)

        # Redirect to a success page or show a message
        messages.success(request, f"Match created successfully")
        return redirect('get_bracket_data', sport_details_id=sport_details.id)
    else:
        return HttpResponse("Invalid request method", status=400)

    



    

from django.db.models import Avg, F
from django.shortcuts import render
from .models import BasketballStats, VolleyballStats, PlayerStats



@login_required
def player_dashboard(request):
    try:
        profile = request.user.profile
        if profile.role == 'Player':
            chat_groups = ChatGroup.objects.all()
            
            sport_profiles = SportProfile.objects.filter(USER_ID=request.user)
            selected_sports = [sp.SPORT_ID.id for sp in sport_profiles]

            query = request.GET.get('q', '')
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

            user = request.user  # Logged-in user
            profile = user.profile

            # Basketball Stats Averages
            basketball_stats = BasketballStats.objects.filter(player_stats__player=user)
            basketball_averages = basketball_stats.aggregate(
                avg_points=Avg('points'),
                avg_rebounds=Avg('rebounds'),
                avg_assists=Avg('assists'),
                avg_blocks=Avg('blocks'),
                avg_steals=Avg('steals'),
                avg_turnovers=Avg('turnovers'),
                avg_three_pointers_made=Avg('three_pointers_made'),
                avg_free_throws_made=Avg('free_throws_made')
            )

            # Volleyball Stats Averages
            volleyball_stats = VolleyballStats.objects.filter(player_stats__player=user)
            volleyball_averages = volleyball_stats.aggregate(
                avg_kills=Avg('kills'),
                avg_blocks=Avg('blocks'),
                avg_blocks_score=Avg('blocks_score'),
                avg_digs=Avg('digs'),
                avg_service_aces=Avg('service_aces'),
                avg_attack_errors=Avg('attack_errors'),
                avg_reception_errors=Avg('reception_errors'),
                avg_assists=Avg('assists')
            )

            context = {
                'basketball_teams': basketball_teams,
                'volleyball_teams': volleyball_teams,
                'my_teams_and_participants': my_teams_and_participants,
                'recent_activities': recent_activities,
                'notifications': notifications,
                'unread_notifications_count': unread_notifications_count,
                'invitations': invitations,
                'chat_groups': chat_groups,
                'basketball_averages': basketball_averages,
                'volleyball_averages': volleyball_averages,
                'profile': profile,
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
            
            # Get pending join requests for the coach's teams
            join_requests = JoinRequest.objects.filter(TEAM_ID__COACH_ID=request.user, STATUS='pending')

            # Get the coach's sport profile
            sport_profile = SportProfile.objects.filter(USER_ID=request.user).first()
            if not sport_profile:
                return redirect('home')  # Redirect if no sport is associated

            # Get the sport associated with the coach's profile
            sport = sport_profile.SPORT_ID

            # Filter TeamCategory by the coach's sport and ensure no duplicates by name
            team_categories = TeamCategory.objects.filter(sport=sport).distinct('name')

            # Initialize the filter form
            filter_form = PlayerFilterForm(request.GET or None, coach=request.user)
            search_query = request.GET.get('search_query')
            position_filters = request.GET.getlist('position')
            
            # Get all notifications for the current user
            notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
            unread_notifications_count = notifications.filter(is_read=False).count()

            # Build the player query based on search and position filters
            players = User.objects.filter(profile__role='Player')
            if sport_profile:
                players = players.filter(profile__sports__SPORT_ID=sport_profile.SPORT_ID)
                
            if search_query:
                players = players.filter(
                    models.Q(profile__FIRST_NAME__icontains=search_query) |
                    models.Q(profile__LAST_NAME__icontains=search_query) |
                    models.Q(username__icontains=search_query)
                )
                
            # Determine the position field based on the coach's sport
            sport_name = sport_profile.SPORT_ID.SPORT_NAME.lower()
            position_field = 'profile__basketball_position_played' if sport_name == 'basketball' else 'profile__volleyball_position_played'   
            
            if position_filters:
                players = players.filter(**{f"{position_field}__in": position_filters})
                
            # Optimize query to select related profile data
            players = players.select_related('profile').distinct()

            # Prepare the context to pass to the template
            context = {
                'teams': teams,
                'players': players,
                'coach_profile': profile,
                'join_requests': join_requests,
                'chat_groups': chat_groups,
                'filter_form': filter_form,
                'notifications': notifications,
                'unread_notifications_count': unread_notifications_count,
                'team_categories': team_categories,
                'coach_sport': sport_profile.SPORT_ID.SPORT_NAME  # Add the coach's sport dynamically to the context
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




def get_bracket_data(request, sport_details_id):
    from math import ceil, log2


    # Get the sport details and event
    sport_details = get_object_or_404(SportDetails, id=sport_details_id)
    event = sport_details.team_category.event  
    event_organizer = event.EVENT_ORGANIZER

    # Get the BracketData object related to this sport
    bracket_data = BracketData.objects.filter(sport_details=sport_details).first()

    if bracket_data:
        # Ensure teams and results are Python objects
        if isinstance(bracket_data.teams, str):
            bracket_teams = json.loads(bracket_data.teams)
        else:
            bracket_teams = bracket_data.teams

        if isinstance(bracket_data.results, str):
            bracket_results = json.loads(bracket_data.results)
        else:
            bracket_results = bracket_data.results

    else:
        # Calculate number of teams
        teams = list(sport_details.teams.all())
        num_teams = len(teams)

        if num_teams == 0:
            # Handle case where no teams are registered
            bracket_teams = []
            bracket_results = []
        else:
            # Ensure the number of teams is a power of 2 by padding with None placeholders
            next_power_of_2 = 2 ** ceil(log2(num_teams))
            padded_teams = teams + [None for _ in range(next_power_of_2 - num_teams)]

            # Generate the bracket teams format
            bracket_teams = [[None if team is not None else None for team in padded_teams[i:i + 2]] for i in range(0, len(padded_teams), 2)]

            # Check the elimination type
            elimination_type = sport_details.elimination_type

            if elimination_type == "single":
                # Single elimination bracket
                num_rounds = ceil(log2(next_power_of_2))  # Number of rounds
                winners_bracket = [[[None, None] for _ in range(next_power_of_2 // (2 ** (r + 1)))] for r in range(num_rounds)]
                bracket_results = [winners_bracket]  # Single elimination has only the winner's bracket
            elif elimination_type == "double":
                # Double elimination bracket
                num_rounds = ceil(log2(next_power_of_2))  # Number of rounds in the winner's bracket

                # Winner's bracket
                winners_bracket = [[[None, None] for _ in range(next_power_of_2 // (2 ** (r + 1)))] for r in range(num_rounds)]

                # Loser's bracket (requires more complex structure)
                losers_bracket = []
                for r in range(num_rounds - 1):
                    matches_in_round = next_power_of_2 // (2 ** (r + 2))
                    losers_bracket.append([[None, None] for _ in range(matches_in_round)])

                # Finals (Grand Final can have two matches if the loser's bracket winner beats the winner's bracket winner)
                finals = [[[None, None]], [[None, None]]]  # Two possible matches for the Grand Final

                bracket_results = [winners_bracket, losers_bracket, finals]

            else:
                # Handle unexpected elimination types (fallback to single elimination as default)
                num_rounds = ceil(log2(next_power_of_2))
                winners_bracket = [[[None, None] for _ in range(next_power_of_2 // (2 ** (r + 1)))] for r in range(num_rounds)]
                bracket_results = [winners_bracket]

            # Save the generated bracket data to the database
            bracket_data = BracketData.objects.create(
                sport_details=sport_details,
                teams=json.dumps(bracket_teams),
                results=json.dumps(bracket_results)
            )

    # Get all matches related to this sport
    matches = Match.objects.filter(sport_details=sport_details)

    # Calculate wins and losses for each team
    wins = {}
    losses = {}

    for match in matches:
        for team in [match.team_a, match.team_b]:
            if team not in wins:
                wins[team] = 0
            if team not in losses:
                losses[team] = 0

        if match.winner:
            wins[match.winner] += 1
            if match.winner == match.team_a:
                losses[match.team_b] += 1
            else:
                losses[match.team_a] += 1

    # Pass the stats to the template
    return render(request, 'ligameet/bracket.html', {
        'sport_details': sport_details,
        'bracket_teams': json.dumps(bracket_teams),  # Ensure JSON format for JavaScript
        'bracket_results': json.dumps(bracket_results),  # Ensure JSON format for JavaScript
        'teams': sport_details.teams.all(),
        'matches': matches,
        'event_organizer': event_organizer,
        'wins': wins,
        'losses': losses,  # Pass wins and losses separately
    })







def save_bracket(request, sport_details_id):
    if request.method == 'POST':
        try:
            # Get the JSON data from the request body
            data = json.loads(request.body)
            
            # Get the SportDetails object based on the provided sport_details_id
            sport_details = SportDetails.objects.get(id=sport_details_id)

            # Update or create bracket data linked with SportDetails
            bracket, created = BracketData.objects.update_or_create(
                sport_details=sport_details,
                defaults={
                    'teams': data['teams'],
                    'results': data['results']
                }
            )
            return JsonResponse({'success': True})
        except SportDetails.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'SportDetails not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)

    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)


def scoreboard_view(request, match_id):
    try:
        # Get the match using the provided match_id
        match = Match.objects.get(id=match_id)
    except Match.DoesNotExist:
        raise Http404("Match not found")

    # Get the sport details for the match (to distinguish between basketball and volleyball)
    sport_details = match.sport_details

    # Teams in the match
    Team_A = match.team_a
    Team_B = match.team_b

    # Get the players for each team
    team_a_players = Team_A.teamparticipant_set.all()
    team_b_players = Team_B.teamparticipant_set.all()

    # Fetch player stats for each player in the match
    team_a_stats = []
    team_b_stats = []
    for player in team_a_players:
        try:
            # Get PlayerStats for the player and match
            player_stats = PlayerStats.objects.get(player=player.USER_ID, match=match)
        except PlayerStats.DoesNotExist:
            player_stats = None
        except PlayerStats.MultipleObjectsReturned:
            # Handle the case of multiple PlayerStats being returned
            player_stats = PlayerStats.objects.filter(player=player.USER_ID, match=match).first()

        if player_stats:
            if sport_details.team_category.sport.SPORT_NAME.lower() == 'basketball':
                basketball_stats = BasketballStats.objects.filter(player_stats=player_stats).first()
                team_a_stats.append(basketball_stats)
            elif sport_details.team_category.sport.SPORT_NAME.lower() == 'volleyball':
                volleyball_stats = VolleyballStats.objects.filter(player_stats=player_stats).first()
                team_a_stats.append(volleyball_stats)
    
    for player in team_b_players:
        try:
            # Get PlayerStats for the player and match
            player_stats = PlayerStats.objects.get(player=player.USER_ID, match=match)
        except PlayerStats.DoesNotExist:
            player_stats = None
        except PlayerStats.MultipleObjectsReturned:
            # Handle the case of multiple PlayerStats being returned
            player_stats = PlayerStats.objects.filter(player=player.USER_ID, match=match).first()

        if player_stats:
            if sport_details.team_category.sport.SPORT_NAME.lower() == 'basketball':
                basketball_stats = BasketballStats.objects.filter(player_stats=player_stats).first()
                team_b_stats.append(basketball_stats)
            elif sport_details.team_category.sport.SPORT_NAME.lower() == 'volleyball':
                volleyball_stats = VolleyballStats.objects.filter(player_stats=player_stats).first()
                team_b_stats.append(volleyball_stats)

    # Zip the lists together for easy rendering in the template
    zipped_team_a = zip(team_a_players, team_a_stats)
    zipped_team_b = zip(team_b_players, team_b_stats)

    # Determine the sport for conditional rendering in the template
    sport = sport_details.team_category.sport.SPORT_NAME.lower()

     
    # Context data for the template
    context = {
        'match': match,
        'Team_A': Team_A,
        'Team_B': Team_B,
        'zipped_team_a': zipped_team_a,
        'zipped_team_b': zipped_team_b,
        'sport': sport,
        
    }

    return render(request, 'ligameet/score_board.html', context)


def edit_player_stats(request, stats_id, sport_name, match_id):
    match = Match.objects.get(id=match_id)
    match.update_scores()
    # First, fetch the PlayerStats instance by player_id
    player_stats = PlayerStats.objects.filter(match_id=match_id).first()
    
    if not player_stats:
        return redirect('scoreboard', match_id=player_stats.match.id if player_stats else None)  # Handle None case for match_id
    
    # Now you can safely get the match_id from the player_stats instance
    match_id = player_stats.match.id

    # # Determine the stats model based on the sport
    # sport_name = player_stats.sport.SPORT_NAME.lower()  # Convert to lowercase for case-insensitive comparison
    if sport_name == 'basketball':  # Check for basketball
        stats = BasketballStats.objects.filter(id=stats_id).first()
        stats_form = BasketballStatsForm
    elif sport_name == 'volleyball':  # Check for volleyball
        stats = VolleyballStats.objects.filter(id=stats_id).first()
        stats_form = VolleyballStatsForm
    else:
        return redirect('scoreboard', match_id=match_id)  # Redirect if sport is not supported or handled

    # Get the stats instance (BasketballStats or VolleyballStats)
    # stats = get_object_or_404(stats_model, player_stats=player_stats)
    
    if request.method == 'POST':
        form = stats_form(request.POST, instance=stats)
        if form.is_valid():
            form.save()
            match.update_scores()
            return redirect('scoreboard', match_id=match_id)  # Redirect after saving
    else:
        form = stats_form(instance=stats)
    
    context = {
        'form': form, 
        'player': player_stats.player,
        'match_id': match_id
    }

    return render(request, 'ligameet/edit_player_stats.html', context)





def edit_match(request, match_id):
    match = get_object_or_404(Match, id=match_id)

    if request.method == 'POST':
        form = MatchForm(request.POST, instance=match)
        if form.is_valid():
            form.save()
            return redirect('get_bracket_data', sport_details_id=match.sport_details.id)  
    else:
        form = MatchForm(instance=match)

    return render(request, 'ligameet/edit_match.html', {'form': form, 'match': match})



def delete_match(request, match_id):
    match = get_object_or_404(Match, id=match_id)

    if request.method == 'POST':
        match.delete()
        messages.success(request, 'Match deleted successfully.')
        return redirect('get_bracket_data', sport_details_id=match.sport_details.id)   

    messages.error(request, 'Invalid request. Match could not be deleted.')
    return redirect('bracket-dashboard')  # Adjust this redirect as needed.
