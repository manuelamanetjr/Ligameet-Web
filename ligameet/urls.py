from django.urls import path
from . import views
from .views import SportListView
from users.views import choose_role

urlpatterns = [
    path('', views.landingpage, name='landingpage'),
    path('home/', SportListView.as_view(), name='home'),
    path('about/', views.about, name='ligameet-about'),
    path('choose-role/', choose_role, name='choose_role'),
    path('event_organizer/', views.eventorglandingpage, name='event_org_landingpage'),
    path('player/', views.player_dashboard, name='player-dashboard'),
    path('create-event/', views.create_event, name='create-event'),
]

