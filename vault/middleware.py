"""
Middleware for the vault app.

Middleware classes:
  1. UpdateLastActivityMiddleware
       - Runs on every authenticated request
       - Updates UserProfile.last_activity to now
       - Logs a 'Logged in' event at the start of each new session

  2. NoCacheAuthenticatedMiddleware  ← SECURITY FIX
       - Adds Cache-Control: no-store headers to ALL authenticated responses
       - Prevents the browser from caching any page that requires login
       - After logout, pressing the Back button will re-request the page
         from the server, which then redirects to login — NEVER shows
         stale cached content
"""

from django.utils import timezone
from vault.models import UserProfile, ActivityLog


class UpdateLastActivityMiddleware:
    """
    Updates last_activity timestamp on every request the logged-in user makes.
    Also creates a 'Logged in' activity log when a new session starts.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Process request BEFORE the view runs
        if request.user.is_authenticated:
            # Get or create the user's profile (safety net for first login)
            profile, _ = UserProfile.objects.get_or_create(user=request.user)

            # Update last_activity to right now
            profile.last_activity = timezone.now()
            profile.save(update_fields=['last_activity'])

            # Log only the first request of a new session as a "Logged in" event
            if not request.session.get('activity_logged'):
                ActivityLog.objects.create(
                    user=request.user,
                    action='Logged in'
                )
                request.session['activity_logged'] = True

        # Pass request to the next middleware / view
        response = self.get_response(request)
        return response


class NoCacheAuthenticatedMiddleware:
    """
    SECURITY MIDDLEWARE — Prevents browser caching of authenticated pages.

    Problem this solves:
        After logout, pressing the browser Back button shows previously
        visited authenticated pages (Dashboard, Assets, Settings, etc.)
        because the browser served them from its local cache without ever
        contacting the server. Django's session/login checks never ran.

    Solution:
        For every response sent to an authenticated user, attach HTTP headers
        that instruct the browser (and any proxy) to NEVER store or reuse
        the response:

            Cache-Control: no-store, no-cache, must-revalidate, max-age=0, private
            Pragma:        no-cache
            Expires:       0

        After logout, when Back is pressed the browser MUST request the page
        fresh from the server. Django's @login_required then fires and
        redirects to the login page immediately.

    Coverage:
        Applied to ALL authenticated responses globally — no view needs
        to be individually decorated.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Apply no-cache headers only for authenticated users.
        # Unauthenticated pages (home, login, register) can be cached normally.
        if request.user.is_authenticated:
            response['Cache-Control'] = (
                'no-store, no-cache, must-revalidate, max-age=0, private'
            )
            response['Pragma']  = 'no-cache'
            response['Expires'] = '0'

        return response
