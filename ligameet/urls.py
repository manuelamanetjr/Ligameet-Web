from django.urls import path
from . import views
from users.views import choose_role, register_user, login_user, reset_password_view, payment_success_sub, payment_cancelled_sub
from django.conf import settings
from django.conf.urls.static import static
from paypal.standard.ipn import views as paypal_views


urlpatterns = [
    path('', views.landingpage, name='landingpage'),
    path('home/', views.home, name='home'),
    path('about/', views.about, name='ligameet-about'),
    path('choose-role/', choose_role, name='choose_role'),
    path('player/', views.player_dashboard, name='player-dashboard'),
    path('scout/', views.scout_dashboard, name='scout-dashboard'),
    path('coach/', views.coach_dashboard, name='coach-dashboard'),
    path('event_organizer/', views.event_dashboard, name='event-dashboard'),
    path('create-event/', views.create_event, name='create-event'),
    path('post-event/<int:event_id>/', views.post_event, name='post-event'),
    path('cancel-event/<int:event_id>/', views.cancel_event, name='cancel-event'),
    path('event-details/<int:event_id>/', views.event_details, name='event-details'),
    path('events/<int:event_id>/sport/<int:sport_id>/edit/', views.edit_sport_details, name='edit-sport-details'),
    path('payment-success/<int:event_id>/<int:sport_id>/', views.payment_success, name='payment-success'),
    path('payment-cancelled/<int:event_id>/', views.payment_cancelled, name='payment-cancelled'),
    path('event/<int:event_id>/sport/<int:sport_id>/team-selection/', views.team_selection, name='team-selection'),
    path('delete-category/<int:category_id>/', views.delete_category, name='delete-category'),
    path('paypal-ipn/', paypal_views.ipn, name='paypal-ipn'),
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
    path('coach/mark_notification_read/', views.coach_mark_notification_read, name='coach_mark_notification_read'),
    path('confirm_invitation/', views.confirm_invitation, name='confirm_invitation'),
    path('api/register/', register_user, name='registerAPI'),
    path('login/register/', login_user, name='loginAPI'),
    path('delete_team/', views.delete_team, name='delete_team'),
    path('register-team/<int:event_id>/', views.register_team, name='register_team'),
    path('get_teams/', views.get_teams, name='get_teams'),
    path('get_coach_name/', views.get_coach_name, name='get_coach_name'),
    path('get-players/<int:team_id>/', views.get_players, name='get_players'),
    path('bracket', views.bracketing_dashboard, name='bracket'),
    path('recruit/<int:player_id>/', views.recruit_player, name='recruit_player'),
    path('get-recruited-players/', views.get_recruited_players, name='get_recruited_players'),
    path('reset-password/', reset_password_view, name='reset_password'),
    path('payment-success-sub/<int:event_id>/<int:sport_id>/', payment_success_sub, name='payment-success-sub'),
    path('payment-cancelled-sub/<int:event_id>/', payment_cancelled_sub, name='payment-cancelled-sub'),
    


    
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)