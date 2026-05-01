"""
Middleware for the vault app.

UpdateLastActivityMiddleware:
  - Runs on EVERY authenticated request
  - Updates UserProfile.last_activity to now
  - This is how we track whether a user is "active"
"""

from django.utils import timezone
from vault.models import UserProfile, ActivityLog


class UpdateLastActivityMiddleware:
    """
    Updates last_activity timestamp on every request the logged-in user makes.
    Also creates a 'login' activity log when a new session starts.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Process request BEFORE the view runs
        if request.user.is_authenticated:
            # Get or create the user's profile (in case it doesn't exist yet)
            profile, created = UserProfile.objects.get_or_create(user=request.user)

            # Update last_activity to right now
            profile.last_activity = timezone.now()
            profile.save(update_fields=['last_activity'])

            # Log the first request of a new session as a "Login" event
            if not request.session.get('activity_logged'):
                ActivityLog.objects.create(
                    user=request.user,
                    action='Logged in'
                )
                request.session['activity_logged'] = True

        # Pass request to the next middleware / view
        response = self.get_response(request)
        return response
