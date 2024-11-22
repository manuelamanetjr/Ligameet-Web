# users/middleware.py

from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from .models import Profile

class RolePickerMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Exclude specific paths from the middleware logic
        excluded_paths = [
            '/choose-role/',  # Already excluded
            '/payment-success-sub/',  # Exclude payment success URL
        ]

        if request.user.is_authenticated:
            profile, created = Profile.objects.get_or_create(user=request.user)

            # Exclude paths that match the excluded_paths list
            if any(request.path.startswith(path) for path in excluded_paths):
                return None

            # Redirect if role, is_scout, or first_login conditions are not met
            if not profile.role and not profile.is_scout and profile.first_login:
                return redirect('choose_role')

        return None
