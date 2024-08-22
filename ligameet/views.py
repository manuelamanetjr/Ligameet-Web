from django.shortcuts import render
from django.http import HttpResponse
from .models import Sport


def home(request):
    context = {
        'sports': Sport.objects.all()
    }
    return render(request, 'ligameet/home.html', context)


def about(request):
    return render(request, 'ligameet/about.html', {'title':'About'})
