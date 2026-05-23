"""
vault/views.py — Main view functions for the Digital Will platform.

Sections:
  1. Inactivity detection helpers
  2. Authentication
  3. Dashboard
  4. Digital Asset CRUD
  5. Nominee management
  6. Activity Log
  7. Settings (multi-section)
"""

import random

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings as django_conf

from .models import DigitalAsset, Nominee, AssetAccess, ActivityLog, UserProfile, ReleaseRequest
from .forms  import RegisterForm, LoginForm, AssetForm, NomineeForm, SettingsForm, AccountInfoForm, PasswordChangeForm
from .utils  import encrypt, decrypt, log_activity


# -----------------------------------------------------------------
# INACTIVITY DETECTION HELPERS
# -----------------------------------------------------------------

INACTIVITY_THRESHOLD_DAYS = 30


def send_release_emails(user, release_request, request=None):
    """Delegate to the OTP-enabled version in otp_views (avoids circular imports)."""
    from .otp_views import send_otp_release_emails
    send_otp_release_emails(user, release_request, request=request)


def check_user_inactivity(request):
    """
    Evaluate inactivity status for the logged-in user.

    Returns dict: {status, days_inactive, threshold, release_request}
    Status values: 'active', 'at_risk', 'triggered'
    """
    user = request.user

    try:
        threshold = user.profile.inactivity_days
    except UserProfile.DoesNotExist:
        threshold = INACTIVITY_THRESHOLD_DAYS

    last_login    = user.last_login
    days_inactive = (timezone.now() - last_login).days if last_login else 0

    at_risk_boundary = int(threshold * 0.7)
    if days_inactive >= threshold:
        inactivity_status = 'triggered'
    elif days_inactive >= at_risk_boundary:
        inactivity_status = 'at_risk'
    else:
        inactivity_status = 'active'

    release_request = None
    if inactivity_status == 'triggered':
        existing = (
            ReleaseRequest.objects
            .filter(user=user)
            .exclude(status='completed')
            .first()
        )
        if existing:
            release_request = existing
            if existing.status == 'pending':
                existing.status       = 'triggered'
                existing.triggered_at = timezone.now()
                existing.notes        = f'Auto-escalated after {days_inactive} days inactive.'
                existing.save()
                log_activity(user, f'Release workflow triggered after {days_inactive} days of inactivity.')
                if not existing.warning_sent_at:
                    send_release_emails(user, existing, request=request)
            elif existing.status == 'triggered' and not existing.warning_sent_at:
                send_release_emails(user, existing, request=request)
        else:
            release_request = ReleaseRequest.objects.create(
                user         = user,
                status       = 'triggered',
                triggered_at = timezone.now(),
                notes        = f'Auto-triggered after {days_inactive} days of inactivity.',
            )
            log_activity(user, f'Release workflow triggered after {days_inactive} days of inactivity.')
            send_release_emails(user, release_request, request=request)
    else:
        release_request = (
            ReleaseRequest.objects
            .filter(user=user)
            .exclude(status='completed')
            .first()
        )

    return {
        'status':          inactivity_status,
        'days_inactive':   days_inactive,
        'threshold':       threshold,
        'release_request': release_request,
    }


# -----------------------------------------------------------------
# HOME
# -----------------------------------------------------------------

def home(request):
    if request.user.is_authenticated:
        return redirect('vault:dashboard')
    return render(request, 'vault/home.html')


# -----------------------------------------------------------------
# AUTHENTICATION
# -----------------------------------------------------------------

def register_view(request):
    if request.user.is_authenticated:
        return redirect('vault:dashboard')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = User.objects.create_user(
            username = form.cleaned_data['username'],
            email    = form.cleaned_data['email'],
            password = form.cleaned_data['password1'],
        )
        UserProfile.objects.create(user=user)
        log_activity(user, 'Account registered')
        messages.success(request, 'Account created! Please log in.')
        return redirect('vault:login')

    return render(request, 'vault/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('vault:dashboard')

    form        = LoginForm(request.POST or None)
    login_error = False

    if request.method == 'POST' and form.is_valid():
        identifier = form.cleaned_data['identifier'].strip()
        password   = form.cleaned_data['password']

        # Auto-detect: email address or username?
        if '@' in identifier:
            # Look up the username that owns this email
            try:
                user_obj = User.objects.get(email__iexact=identifier)
                username = user_obj.username
            except User.DoesNotExist:
                username = identifier        # Will fail authenticate() — intentional
            except User.MultipleObjectsReturned:
                username = identifier        # Fail safely on duplicate emails
        else:
            username = identifier            # Treat as plain username

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('vault:dashboard')
        else:
            login_error = True

    return render(request, 'vault/login.html', {'form': form, 'login_error': login_error})


def logout_view(request):
    if request.user.is_authenticated:
        log_activity(request.user, 'Logged out')

    logout(request)
    request.session.flush()

    response = redirect('vault:home')
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
    response['Pragma']  = 'no-cache'
    response['Expires'] = '0'
    return response


@login_required
def delete_account(request):
    """
    Permanently deletes the authenticated user's account and ALL associated
    data: UserProfile, DigitalAssets, Nominees, ActivityLogs, ReleaseRequests.

    Requires POST + correct password confirmation.
    Logs out and flushes session BEFORE deletion so no stale session remains.
    Django's CASCADE foreign keys handle the data cleanup automatically.
    """
    if request.method != 'POST':
        return redirect('vault:settings')

    confirm_password = request.POST.get('confirm_password', '').strip()
    user = request.user   # Keep reference — logout() will change request.user

    # Verify the user knows their own password before we destroy anything
    if not user.check_password(confirm_password):
        messages.error(
            request,
            'Incorrect password. Your account was NOT deleted. Please try again.'
        )
        return redirect('vault:settings')

    # Record the deletion event (deleted with the user, but good for any server-side logs)
    try:
        ActivityLog.objects.create(user=user, action='Account permanently deleted by user')
    except Exception:
        pass

    # Logout + flush session BEFORE deleting the user object
    logout(request)
    request.session.flush()

    # Delete the user — Django CASCADE removes:
    #   UserProfile, DigitalAsset(s), Nominee(s), ActivityLog(s), ReleaseRequest(s)
    user.delete()

    response = redirect('vault:home')
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
    return response


# -----------------------------------------------------------------
# DASHBOARD
# -----------------------------------------------------------------

@login_required
def dashboard(request):
    profile  = get_object_or_404(UserProfile, user=request.user)
    assets   = DigitalAsset.objects.filter(user=request.user)
    nominees = Nominee.objects.filter(user=request.user)
    logs     = ActivityLog.objects.filter(user=request.user)[:8]

    inactivity = check_user_inactivity(request)

    category_counts = {
        'password': assets.filter(category='password').count(),
        'document': assets.filter(category='document').count(),
        'note':     assets.filter(category='note').count(),
    }

    return render(request, 'vault/dashboard.html', {
        'profile':           profile,
        'assets':            assets,
        'nominees':          nominees,
        'logs':              logs,
        'category_counts':   category_counts,
        'total_assets':      assets.count(),
        'inactivity_status': inactivity['status'],
        'days_inactive':     inactivity['days_inactive'],
        'threshold':         inactivity['threshold'],
        'release_request':   inactivity['release_request'],
        'last_login':        request.user.last_login,
        'is_at_risk':        inactivity['status'] in ('at_risk', 'triggered'),
        'days_since':        inactivity['days_inactive'],
    })


# -----------------------------------------------------------------
# DIGITAL ASSETS  (CRUD)
# -----------------------------------------------------------------

@login_required
def asset_list(request):
    category   = request.GET.get('category', 'all')
    all_assets = DigitalAsset.objects.filter(user=request.user)
    assets     = all_assets.filter(category=category) if category != 'all' else all_assets

    category_counts = {
        'password': all_assets.filter(category='password').count(),
        'document': all_assets.filter(category='document').count(),
        'note':     all_assets.filter(category='note').count(),
    }
    return render(request, 'vault/asset_list.html', {
        'assets':          assets,
        'category_counts': category_counts,
        'active_category': category,
    })


@login_required
def asset_add(request):
    form = AssetForm(request.POST or None, request.FILES or None)
    form.fields['nominees'].queryset = Nominee.objects.filter(user=request.user)

    if request.method == 'POST' and form.is_valid():
        asset      = form.save(commit=False)
        asset.user = request.user
        category   = form.cleaned_data['category']

        if category == 'document' and form.cleaned_data.get('document_file'):
            asset.encrypted_data = ''
        else:
            content = form.cleaned_data.get('encrypted_data', '')
            asset.encrypted_data = encrypt(content) if content else ''
            asset.document_file  = None

        asset.save()
        form.save_m2m()
        log_activity(request.user, f'Added asset: {asset.title}')
        messages.success(request, f'"{asset.title}" added to your vault.')
        return redirect('vault:asset_list')

    return render(request, 'vault/asset_form.html', {'form': form, 'action': 'Add'})


@login_required
def asset_detail(request, pk):
    asset     = get_object_or_404(DigitalAsset, pk=pk, user=request.user)
    decrypted = None
    file_url  = None

    if asset.document_file:
        file_url = asset.document_file.url
    elif asset.encrypted_data:
        decrypted = decrypt(asset.encrypted_data)

    return render(request, 'vault/asset_detail.html', {
        'asset':     asset,
        'decrypted': decrypted,
        'file_url':  file_url,
    })


@login_required
def asset_edit(request, pk):
    asset        = get_object_or_404(DigitalAsset, pk=pk, user=request.user)
    initial_data = {'encrypted_data': decrypt(asset.encrypted_data) if asset.encrypted_data else ''}

    form = AssetForm(request.POST or None, request.FILES or None, instance=asset, initial=initial_data)
    form.fields['nominees'].queryset = Nominee.objects.filter(user=request.user)

    if request.method == 'POST' and form.is_valid():
        asset    = form.save(commit=False)
        category = form.cleaned_data['category']
        new_file = form.cleaned_data.get('document_file')

        if category == 'document' and new_file:
            asset.document_file  = new_file
            asset.encrypted_data = ''
        elif category == 'document' and asset.document_file and not form.cleaned_data.get('encrypted_data'):
            pass
        else:
            asset.encrypted_data = encrypt(form.cleaned_data['encrypted_data'])
            asset.document_file  = None

        asset.save()
        form.save_m2m()
        log_activity(request.user, f'Updated asset: {asset.title}')
        messages.success(request, f'"{asset.title}" updated.')
        return redirect('vault:asset_list')

    return render(request, 'vault/asset_form.html', {'form': form, 'action': 'Edit', 'asset': asset})


@login_required
def asset_delete(request, pk):
    asset = get_object_or_404(DigitalAsset, pk=pk, user=request.user)
    if request.method == 'POST':
        title = asset.title
        asset.delete()
        log_activity(request.user, f'Deleted asset: {title}')
        messages.success(request, f'"{title}" deleted.')
        return redirect('vault:asset_list')
    return render(request, 'vault/asset_confirm_delete.html', {'asset': asset})


# -----------------------------------------------------------------
# NOMINEES
# -----------------------------------------------------------------

@login_required
def nominee_list(request):
    nominees = Nominee.objects.filter(user=request.user)
    return render(request, 'vault/nominee_list.html', {'nominees': nominees})


@login_required
def nominee_add(request):
    form = NomineeForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        nominee      = form.save(commit=False)
        nominee.user = request.user
        nominee.save()
        log_activity(request.user, f'Added nominee: {nominee.name}')
        messages.success(request, f'{nominee.name} added as a nominee.')
        return redirect('vault:nominee_list')
    return render(request, 'vault/nominee_form.html', {'form': form, 'action': 'Add'})


@login_required
def nominee_delete(request, pk):
    nominee = get_object_or_404(Nominee, pk=pk, user=request.user)
    if request.method == 'POST':
        name = nominee.name
        nominee.delete()
        log_activity(request.user, f'Removed nominee: {name}')
        messages.success(request, f'{name} removed.')
        return redirect('vault:nominee_list')
    return render(request, 'vault/nominee_confirm_delete.html', {'nominee': nominee})


@login_required
def nominee_assign(request, pk):
    nominee     = get_object_or_404(Nominee, pk=pk, user=request.user)
    user_assets = DigitalAsset.objects.filter(user=request.user)

    if request.method == 'POST':
        selected_ids = request.POST.getlist('assets')
        for asset in user_assets:
            if str(asset.pk) in selected_ids:
                asset.nominees.add(nominee)
            else:
                asset.nominees.remove(nominee)
        log_activity(request.user, f'Updated assignments for nominee: {nominee.name}')
        messages.success(request, f'Assets updated for {nominee.name}.')
        return redirect('vault:nominee_list')

    assigned_ids = set(
        DigitalAsset.objects.filter(user=request.user, nominees=nominee)
        .values_list('pk', flat=True)
    )
    return render(request, 'vault/nominee_assign.html', {
        'nominee':      nominee,
        'assets':       user_assets,
        'assigned_ids': assigned_ids,
    })


# -----------------------------------------------------------------
# ACTIVITY LOG
# -----------------------------------------------------------------

@login_required
def activity_log(request):
    logs = ActivityLog.objects.filter(user=request.user)
    return render(request, 'vault/activity_log.html', {'logs': logs})


# -----------------------------------------------------------------
# SETTINGS  (multi-section)
# -----------------------------------------------------------------

@login_required
def settings_view(request):
    """
    Multi-section settings page.
    Each form section POSTs with a hidden 'action' field for independent processing.
    """
    profile  = get_object_or_404(UserProfile, user=request.user)
    nominees = Nominee.objects.filter(user=request.user)

    profile_form  = SettingsForm(instance=profile)
    account_form  = AccountInfoForm(instance=request.user)
    password_form = PasswordChangeForm(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'profile':
            profile_form = SettingsForm(request.POST, instance=profile)
            if profile_form.is_valid():
                profile_form.save()
                log_activity(request.user, 'Updated security settings')
                messages.success(request, 'Security settings saved.')
                return redirect('vault:settings')

        elif action == 'account':
            account_form = AccountInfoForm(request.POST, instance=request.user)
            if account_form.is_valid():
                account_form.save()
                log_activity(request.user, 'Updated account information')
                messages.success(request, 'Account info updated.')
                return redirect('vault:settings')

        elif action == 'password':
            password_form = PasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                log_activity(request.user, 'Changed account password')
                messages.success(request, 'Password changed successfully.')
                return redirect('vault:settings')

        elif action == 'clear_logs':
            ActivityLog.objects.filter(user=request.user).delete()
            messages.warning(request, 'Activity log cleared.')
            return redirect('vault:settings')

    return render(request, 'vault/settings.html', {
        'profile':       profile,
        'nominees':      nominees,
        'profile_form':  profile_form,
        'account_form':  account_form,
        'password_form': password_form,
    })
