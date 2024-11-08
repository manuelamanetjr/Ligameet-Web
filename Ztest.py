from django.conf import settings
from paypal.standard.forms import PayPalPaymentsForm
from django.urls import reverse


@login_required
def event_details(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    event.update_status()
    sports_with_requirements = []

    # Loop through each sport associated with the event
    for sport in event.SPORT.all():
        try:
            sport_requirement = SportRequirement.objects.get(sport=sport, event=event)

            # PayPal form configuration
            paypal_dict = {
                'business': settings.PAYPAL_RECEIVER_EMAIL,
                'amount': sport_requirement.entrance_fee,
                'item_name': f'Registration for {sport.SPORT_NAME} - {event.EVENT_NAME}',
                'invoice': f"{event_id}-{sport.id}",
                'currency_code': 'PHP',
                'notify_url': request.build_absolute_uri(reverse('paypal-ipn')),
                'return_url': request.build_absolute_uri(reverse('payment-success', args=[event_id, sport.id])),
                'cancel_return': request.build_absolute_uri(reverse('payment-cancelled', args=[event_id])),
            }

            # Initialize PayPal form
            form = PayPalPaymentsForm(initial=paypal_dict)

            # Append sport details with the form
            sports_with_requirements.append({
                'sport': sport,
                'requirement': sport_requirement,
                'paypal_form': form,
            })
        except SportRequirement.DoesNotExist:
            # Handle case where no requirements exist for the sport
            sports_with_requirements.append({
                'sport': sport,
                'requirement': None,
                'paypal_form': None,
            })

    context = {
        'event': event,
        'sports_with_requirements': sports_with_requirements,
    }

    return render(request, 'ligameet/event_details.html', context)

