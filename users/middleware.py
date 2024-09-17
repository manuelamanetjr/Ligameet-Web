# users/middleware.py

from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from .models import Profile

class RolePickerMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.user.is_authenticated:
            profile, created = Profile.objects.get_or_create(user=request.user)
            if not profile.role:
                if not request.path.startswith('/choose-role/'):
                    return redirect('choose_role')
