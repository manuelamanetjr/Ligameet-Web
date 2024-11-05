from django.urls import path
from . import views
from .views import SportListView
from users.views import choose_role, register_user, login_user
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.landingpage, name='landingpage'),
    path('home/', SportListView.as_view(), name='home'),
    path('about/', views.about, name='ligameet-about'),
    path('choose-role/', choose_role, name='choose_role'),
    path('player/', views.player_dashboard, name='player-dashboard'),
    path('scout/', views.scout_dashboard, name='scout-dashboard'),
    path('coach/', views.coach_dashboard, name='coach-dashboard'),
    path('event_organizer/', views.event_dashboard, name='event-dashboard'),
    path('create-event/', views.create_event, name='create-event'),
    path('event-details/<int:event_id>/', views.event_details, name='event-details'),
    path('join_team/<int:team_id>/', views.join_team_request, name='join_team_request'),
    path('approve_join_request/<int:join_request_id>/', views.approve_join_request, name='approve_join_request'),
    path('decline_join_request/<int:join_request_id>/', views.decline_join_request, name='decline_join_request'),
    path('leave-team/<int:team_id>/', views.leave_team, name='leave-team'),
    path('poke-player/<int:player_id>/', views.poke, name='poke'),
    path('mark_notification/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('mark_all_notifications_as_read/', views.mark_all_notifications_as_read, name='mark_all_notifications_as_read'),
    path('poke_back/<int:notification_id>/', views.poke_back, name='poke_back'),
    path('create_team/', views.create_team, name='create_team'),
    path('get_team_players/', views.get_team_players, name='get_team_players'),
    path('remove_player_from_team/', views.remove_player_from_team, name='remove_player_from_team'),
    path('manage_team/', views.manage_team, name='manage_team'),
    path('send_invite/', views.send_invite, name='send_invite'),
    path('confirm_invitation/', views.confirm_invitation, name='confirm_invitation'),
    path('api/register/', register_user, name='registerAPI'),
    path('login/register/', login_user, name='loginAPI'),
    path('delete_team/', views.delete_team, name='delete_team'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)