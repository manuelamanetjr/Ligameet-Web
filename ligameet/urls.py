from django.urls import path
from . import views
from users.views import choose_role, register_user, login_user, get_sports, get_events, get_invitations, update_invitation_status, reset_password_view, payment_success_sub, payment_cancelled_sub, fetch_account_details, update_account_details, update_user_sport, fetch_teams, join_team
from django.conf import settings
from django.conf.urls.static import static
from paypal.standard.ipn import views as paypal_views
from users import views as user_views


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
    path('payment-success/<int:event_id>/<int:category_id>/', views.payment_success, name='payment-success'),
    path('payment-cancelled/<int:event_id>/', views.payment_cancelled, name='payment-cancelled'),
    path('pay-with-wallet/', views.pay_with_wallet, name='pay-with-wallet'),
    path('event/<int:event_id>/sport/<int:category_id>/team-selection/', views.team_selection, name='team-selection'),
    path('leave_game/<int:sport_id>/<int:team_category_id>/', views.leave_game, name='leave-game'),
    path('delete-category/<int:category_id>/', views.delete_category, name='delete-category'),
    path('wallet/', views.wallet_dashboard, name='wallet-dashboard'),
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

    path('delete_team/', views.delete_team, name='delete_team'),
    path('register-team/<int:event_id>/', views.register_team, name='register_team'),
    path('get_teams/', views.get_teams, name='get_teams'),
    path('get_coach_name/', views.get_coach_name, name='get_coach_name'),
    path('get-players/<int:team_id>/', views.get_players, name='get_players'),
    path('bracket', views.bracketing_dashboard, name='bracket'),
    path('recruit/<int:player_id>/', views.recruit_player, name='recruit_player'),
    path('get-recruited-players/', views.get_recruited_players, name='get_recruited_players'),
    path('reset-password/', reset_password_view, name='reset_password'),
    path('payment-success-sub/<int:profile_id>/', user_views.payment_success_sub, name='payment-success-sub'),
    path('payment-cancelled-sub/', user_views.payment_cancelled_sub, name='payment-cancelled-sub'),
    path('create-match/', views.create_match, name='create-match'),
    path('create-match/<int:event_id>/', views.create_match, name='create-match'),
    path('event_mark_notification_read/', views.event_mark_notification_read, name='event_mark_notification_read'),
    path('event/notifications_view/', views.event_notifications_view, name='event_notifications_view'),

    
    path('api/register/', register_user, name='registerAPI'),
    path('api/login/', login_user, name='loginAPI'),
    path('api/sports/', get_sports, name='get_sports'),
    path('api/events/', get_events, name='get-events'),
    path('api/invitations/<int:user_id>/', get_invitations, name='get-invitations'),
    path('api/invitations/update/', update_invitation_status, name='update_invitation_status'),
    path('api/account/fetch/', fetch_account_details, name='fetch_account'),
    path('api/account/update/', update_account_details, name='update_account'),
    path('api/sport/update/', update_user_sport, name='update_sport'),
    path('api/fetch/teams/', fetch_teams, name='fetch_teams'),
    path('api/join/team/', join_team, name='join_team'),
    



    
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)