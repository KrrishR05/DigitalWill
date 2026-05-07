"""
otp_views.py — Nominee OTP verification and asset access views.

These views are intentionally kept separate from views.py so they can
be cleanly maintained and extended without touching the main view file.

Views:
  send_otp_release_emails()  — generates OTPs and emails nominees
  nominee_verify()           — public OTP entry page (no login needed)
  nominee_access()           — decrypted asset viewer for verified nominees
  test_send_otp()            — manually trigger OTP emails for testing
"""

import random

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings as django_settings
from django.utils import timezone

from .models import Nominee, DigitalAsset, ReleaseRequest, ActivityLog
from .utils import decrypt, log_activity


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: Generate OTP and send email to one nominee
# ─────────────────────────────────────────────────────────────────────────────

def _generate_otp(nominee):
    """Generate a fresh 6-digit OTP, save it, and return the string."""
    otp = str(random.randint(100000, 999999))
    nominee.otp          = otp
    nominee.otp_verified = False
    nominee.save(update_fields=['otp', 'otp_verified'])
    return otp


def _strip_emoji(text):
    """Remove emoji and any non-ASCII characters from a string (safe for SMTP)."""
    return text.encode('ascii', 'ignore').decode('ascii').strip()


def send_otp_release_emails(user, release_request, request=None):
    """
    Generate unique OTPs for every nominee and send them a release notification.

    Email content is intentionally ASCII-only to ensure compatibility with
    all SMTP servers and avoid codec encoding errors.
    """
    nominees = Nominee.objects.filter(user=user)
    if not nominees.exists():
        log_activity(user, 'Release triggered but no nominees configured -- no emails sent.')
        return

    base_url = (
        f"{request.scheme}://{request.get_host()}"
        if request
        else 'http://127.0.0.1:8000'
    )

    sent_count = 0
    for nominee in nominees:
        # ── Generate and save a fresh 6-digit OTP ────────────────────
        otp = _generate_otp(nominee)
        verify_url = f"{base_url}/access/verify/{nominee.pk}/"

        # ── Build ASCII-safe asset list ───────────────────────────────
        assigned = DigitalAsset.objects.filter(user=user, nominees=nominee)
        if assigned.exists():
            asset_lines = "\n".join(
                # strip_emoji removes emoji like 🔑 📄 📝 from category display
                f"  - {a.title}  [{_strip_emoji(a.get_category_display())}]"
                for a in assigned
            )
        else:
            asset_lines = "  (All assets of the account holder)"

        owner = _strip_emoji(user.get_full_name() or user.username)

        # Subject: ASCII only -- no em-dashes, no special chars
        subject = f"[Digital Will] Access granted by {owner} - Your OTP inside"

        # Body: all ASCII -- use = and - for separators, * for bullets
        body = (
            f"Dear {nominee.name},\n\n"
            f"This is an automated notification from Digital Will Platform.\n\n"
            f"{'=' * 56}\n"
            f"  {owner} has been inactive for an extended period.\n"
            f"  You have been designated as a trusted nominee.\n"
            f"{'=' * 56}\n\n"
            f"ASSETS YOU HAVE BEEN GRANTED ACCESS TO:\n"
            f"{asset_lines}\n\n"
            f"{'-' * 56}\n"
            f"  YOUR ONE-TIME PASSWORD (OTP)  :  {otp}\n"
            f"{'-' * 56}\n\n"
            f"HOW TO ACCESS:\n"
            f"  1. Open this link in your browser:\n"
            f"     {verify_url}\n"
            f"  2. Enter the OTP shown above.\n"
            f"  3. You will see your assigned assets immediately.\n\n"
            f"SECURITY NOTICE:\n"
            f"  * This OTP is unique to you -- do not share it.\n"
            f"  * It remains valid until revoked by the account holder.\n\n"
            f"Release Request #: {release_request.pk}\n"
            f"Triggered on     : {timezone.now().strftime('%d %B %Y at %H:%M IST')}\n\n"
            f"-- Digital Will Platform\n"
            f"This is an automated message. Please do not reply."
        )

        try:
            send_mail(
                subject        = subject,
                message        = body,
                from_email     = django_settings.DEFAULT_FROM_EMAIL,
                recipient_list = [nominee.email],
                fail_silently  = False,
            )
            sent_count += 1
            log_activity(user, f'OTP email sent to nominee: {nominee.name} <{nominee.email}>')
        except Exception as exc:
            log_activity(user, f'Failed to send OTP email to {nominee.email}: {exc}')

    # Mark dispatched -- prevents re-send on next dashboard load
    release_request.warning_sent_at = timezone.now()
    release_request.notes = (
        f"{release_request.notes or ''} "
        f"| OTP emails sent to {sent_count}/{nominees.count()} nominee(s) "
        f"on {timezone.now().strftime('%d %b %Y %H:%M IST')}."
    ).strip()
    release_request.save(update_fields=['warning_sent_at', 'notes'])


# ─────────────────────────────────────────────────────────────────────────────
# VIEW 1: NOMINEE OTP VERIFICATION  (PUBLIC — no login required)
# URL: /access/verify/<pk>/
# ─────────────────────────────────────────────────────────────────────────────

def nominee_verify(request, pk):
    """
    Public page where a nominee enters their OTP to verify identity.
    No Django account required — accessed directly from the email link.

    On success:
      - Sets nominee.otp_verified = True
      - Stores a session key to allow access to nominee_access
      - Redirects to nominee_access page
    """
    nominee = get_object_or_404(Nominee, pk=pk)

    # If already verified in this session, go straight to assets
    if request.session.get(f'nominee_verified_{pk}'):
        return redirect('vault:nominee_access', pk=pk)

    error = None

    if request.method == 'POST':
        entered = request.POST.get('otp', '').strip()

        if not nominee.otp:
            error = 'No OTP has been generated for you yet. Please wait for the release notification email.'

        elif entered == nominee.otp:
            # ✅ OTP matches — verify and open access
            nominee.otp_verified = True
            nominee.save(update_fields=['otp_verified'])
            request.session[f'nominee_verified_{pk}'] = True
            request.session.set_expiry(86400)  # session lasts 24 hours
            log_activity(
                nominee.user,
                f'Nominee {nominee.name} ({nominee.email}) verified OTP successfully.'
            )
            messages.success(request, f'Identity verified! Welcome, {nominee.name}.')
            return redirect('vault:nominee_access', pk=pk)

        else:
            error = 'Invalid OTP. Please double-check your email and try again.'

    return render(request, 'vault/nominee_verify.html', {
        'nominee': nominee,
        'error':   error,
        'owner':   nominee.user.get_full_name() or nominee.user.username,
    })


# ─────────────────────────────────────────────────────────────────────────────
# VIEW 2: NOMINEE ASSET ACCESS  (PUBLIC — OTP-gated)
# URL: /access/<pk>/
# ─────────────────────────────────────────────────────────────────────────────

def nominee_access(request, pk):
    """
    Shows the decrypted/downloadable assets assigned to a verified nominee.

    Security:
      - Requires nominee.otp_verified == True AND a valid session key.
      - Without both, redirects to the OTP verification page.
      - Never exposes assets belonging to other users.
    """
    nominee = get_object_or_404(Nominee, pk=pk)

    session_ok = request.session.get(f'nominee_verified_{pk}', False)
    if not (nominee.otp_verified and session_ok):
        messages.warning(request, 'Please verify your identity with your OTP first.')
        return redirect('vault:nominee_verify', pk=pk)

    # ── Build decrypted asset list ────────────────────────────────────────
    raw_assets = DigitalAsset.objects.filter(nominees=nominee)
    asset_data = []
    for asset in raw_assets:
        decrypted = None
        file_url  = None

        if asset.document_file:
            file_url = asset.document_file.url
        elif asset.encrypted_data:
            try:
                decrypted = decrypt(asset.encrypted_data)
            except Exception:
                decrypted = '[Content could not be decrypted — contact the platform.]'

        asset_data.append({
            'asset':     asset,
            'decrypted': decrypted,
            'file_url':  file_url,
        })

    # ── Retrieve owner's final message (if any) ───────────────────────────
    try:
        final_message = nominee.user.profile.final_message
    except Exception:
        final_message = None

    owner = nominee.user.get_full_name() or nominee.user.username

    return render(request, 'vault/nominee_access.html', {
        'nominee':       nominee,
        'owner':         owner,
        'asset_data':    asset_data,
        'final_message': final_message,
    })


# ─────────────────────────────────────────────────────────────────────────────
# VIEW 3: TEST OTP TRIGGER  (LOGIN REQUIRED)
# URL: /settings/test-otp/     POST only
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def test_send_otp(request):
    """
    Manually sends OTP release emails to ALL nominees.
    Used for testing without waiting for real inactivity.
    POST only, CSRF protected. Always sends fresh emails.
    """
    if request.method != 'POST':
        return redirect('vault:settings')

    nominees = Nominee.objects.filter(user=request.user)
    if not nominees.exists():
        messages.warning(request, 'Add at least one nominee before testing.')
        return redirect('vault:settings')

    # Get or create a triggered release request
    release_req, created = ReleaseRequest.objects.get_or_create(
        user   = request.user,
        status = 'triggered',
        defaults={
            'triggered_at': timezone.now(),
            'notes':        'Manual test trigger from Settings page.',
        }
    )

    # Always reset so emails fire fresh even if previously dispatched
    release_req.warning_sent_at = None
    release_req.triggered_at    = timezone.now()
    if not created:
        release_req.notes = (release_req.notes or '') + ' | Re-triggered from test button.'
    release_req.save(update_fields=['warning_sent_at', 'triggered_at', 'notes'])

    # Reset nominee OTP state so they can re-verify after a fresh test
    nominees.update(otp_verified=False)

    # Send fresh OTP emails (ASCII-only content)
    send_otp_release_emails(request.user, release_req, request=request)

    count = nominees.count()
    messages.success(
        request,
        f'Test OTP emails sent to {count} nominee(s)! '
        f'Check their inbox -- each email has a unique 6-digit OTP and verification link.'
    )
    log_activity(request.user, f'Test OTP emails sent to {count} nominee(s).')
    return redirect('vault:settings')
