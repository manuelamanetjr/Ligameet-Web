from django.contrib import admin
from .models import Sport, Event, Wallet, File, Team, TeamParticipant, TeamEvent, Match, Subscription, TeamRegistrationFee, SportsEvent, TeamMatch, UserMatch, VolleyballStats, SportProfile, UserRegistrationFee, Payment, Transaction, JoinRequest, Activity, Notification, Invitation, TeamCategory, SportDetails

class JoinRequestAdmin(admin.ModelAdmin):
    list_display = ('USER_ID', 'TEAM_ID', 'STATUS', 'REQUEST_DATE')

    def save_model(self, request, obj, form, change):
        # Call the default save method
        super().save_model(request, obj, form, change)

        # Check if the status is changed to approved
        if obj.STATUS == 'approved':
            # Create TeamParticipant if it doesn't already exist
            if not TeamParticipant.objects.filter(USER_ID=obj.USER_ID, TEAM_ID=obj.TEAM_ID).exists():
                TeamParticipant.objects.create(USER_ID=obj.USER_ID, TEAM_ID=obj.TEAM_ID)
                
admin.site.register(Sport)
admin.site.register(Event)
admin.site.register(Wallet)
admin.site.register(File)
admin.site.register(Team)
admin.site.register(TeamParticipant)
admin.site.register(TeamEvent)
admin.site.register(Match)
admin.site.register(Subscription)
admin.site.register(TeamRegistrationFee)
admin.site.register(SportsEvent)
admin.site.register(SportProfile)
admin.site.register(TeamMatch)
admin.site.register(UserMatch)
admin.site.register(VolleyballStats)
admin.site.register(UserRegistrationFee)
admin.site.register(Payment)
admin.site.register(Transaction)
admin.site.register(JoinRequest)
admin.site.register(Activity)
admin.site.register(Notification)
admin.site.register(Invitation)
admin.site.register(TeamCategory)
admin.site.register(SportDetails)



