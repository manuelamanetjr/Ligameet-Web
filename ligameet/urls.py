from django.urls import path
from . import views
from .views import SportListView

urlpatterns = [
    path('', SportListView.as_view(), name='ligameet-home'),
    path('about/', views.about, name='ligameet-about'),

]

