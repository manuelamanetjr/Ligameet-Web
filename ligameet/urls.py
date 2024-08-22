from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='ligameet-home'),
    path('about/', views.about, name='ligameet-about'),

]

