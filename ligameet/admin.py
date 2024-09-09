from django.contrib import admin
from .models import Sport, Event, Participant, Wallet, File, Team, TeamParticipant, TeamEvent, Match, Subscription, TeamRegistrationFee, SportsEvent, TeamMatch, UserMatch, VolleyballStats, UserRegistrationFee, Payment, Transaction

admin.site.register(Sport)
admin.site.register(Event)
admin.site.register(Participant)
admin.site.register(Wallet)
admin.site.register(File)
admin.site.register(Team)
admin.site.register(TeamParticipant)
admin.site.register(TeamEvent)
admin.site.register(Match)
admin.site.register(Subscription)
admin.site.register(TeamRegistrationFee)
admin.site.register(SportsEvent)
admin.site.register(TeamMatch)
admin.site.register(UserMatch)
admin.site.register(VolleyballStats)
admin.site.register(UserRegistrationFee)
admin.site.register(Payment)
admin.site.register(Transaction)


