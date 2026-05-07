"""
_setup_otp.py  —  Run once from project root:
    python _setup_otp.py

This script:
  1. Re-encodes views.py as clean UTF-8 (no BOM)
  2. Adds `import random` if missing
  3. Replaces send_release_emails() with the OTP-enabled version
  4. Appends nominee_verify, nominee_access, test_send_otp views
"""
import re, os, sys

VIEWS_PATH = os.path.join(os.path.dirname(__file__), 'vault', 'views.py')

# ── Read (handle BOM) ────────────────────────────────────────────────────────
with open(VIEWS_PATH, 'rb') as f:
    raw = f.read()

# Strip BOM if present
BOM = b'\xef\xbb\xbf'
if raw.startswith(BOM):
    raw = raw[len(BOM):]
    print('[+] Stripped UTF-8 BOM')

src = raw.decode('utf-8', errors='replace')

# ── 1. Add `import random` ───────────────────────────────────────────────────
if 'import random' not in src:
    src = src.replace(
        'from django.core.mail import send_mail',
        'import random\nfrom django.core.mail import send_mail',
        1,
    )
    print('[+] Added: import random')
else:
    print('[=] import random already present')

# ── 2. Replace send_release_emails() ────────────────────────────────────────
NEW_FUNC = r'''def send_release_emails(user, release_request, request=None):
    """
    Send personalised OTP release emails to every nominee of `user`.

    For each nominee:
      1. Generate a fresh 6-digit OTP and save it to nominee.otp
      2. Build a verification URL  (/access/verify/<nominee_pk>/)
      3. Email OTP + link so the nominee can verify identity and view assets

    Errors are caught/logged so they never crash the caller.
    Called exactly once per release event (guarded by warning_sent_at).
    """
    nominees = Nominee.objects.filter(user=user)
    if not nominees.exists():
        log_activity(user, 'Release triggered but no nominees configured - no emails sent.')
        return

    base_url = (
        f"{request.scheme}://{request.get_host()}" if request
        else 'http://127.0.0.1:8000'
    )

    sent_count = 0
    for nominee in nominees:
        # ---- Generate & save fresh 6-digit OTP for this nominee ----
        otp = str(random.randint(100000, 999999))
        nominee.otp = otp
        nominee.otp_verified = False
        nominee.save(update_fields=['otp', 'otp_verified'])

        verify_url = f"{base_url}/access/verify/{nominee.pk}/"

        # ---- Collect assigned assets ----
        assigned_assets = DigitalAsset.objects.filter(user=user, nominees=nominee)
        if assigned_assets.exists():
            asset_lines = "\n".join(
                f"  - {a.title}  [{a.get_category_display()}]"
                for a in assigned_assets
            )
        else:
            asset_lines = "  (All assets of the account holder)"

        owner = user.get_full_name() or user.username
        subject = f"[Digital Will] Access granted by {owner} - Your OTP inside"
        body = (
            f"Dear {nominee.name},\n\n"
            f"This is an automated notification from Digital Will Platform.\n\n"
            f"{'=' * 54}\n"
            f"  {owner} has been inactive for an extended period.\n"
            f"  You have been designated as a trusted nominee.\n"
            f"{'=' * 54}\n\n"
            f"ASSETS YOU CAN ACCESS:\n{asset_lines}\n\n"
            f"{'-' * 54}\n"
            f"  YOUR ONE-TIME PASSWORD (OTP): {otp}\n"
            f"{'-' * 54}\n\n"
            f"To view the assets, visit this link and enter your OTP:\n"
            f"  {verify_url}\n\n"
            f"This OTP is unique to you. Do not share it.\n\n"
            f"Release Request #: {release_request.pk}\n"
            f"Triggered on     : {timezone.now().strftime('%d %B %Y at %H:%M IST')}\n\n"
            f"-- Digital Will Platform\n"
            f"This is an automated message. Please do not reply."
        )

        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[nominee.email],
                fail_silently=False,
            )
            sent_count += 1
            log_activity(user, f'OTP release email sent to {nominee.name} <{nominee.email}>')
        except Exception as exc:
            log_activity(user, f'Failed to send release email to {nominee.email}: {exc}')

    # Mark dispatched - prevents re-send on next dashboard load
    release_request.warning_sent_at = timezone.now()
    release_request.notes = (
        f'{release_request.notes or ""} '
        f'| OTP emails sent to {sent_count}/{nominees.count()} nominee(s) '
        f'on {timezone.now().strftime("%d %b %Y %H:%M IST")}.'
    ).strip()
    release_request.save(update_fields=['warning_sent_at', 'notes'])
'''

MARKER = 'def send_release_emails('
if MARKER in src:
    idx_start = src.index(MARKER)
    # Find next top-level function/class after it
    rest = src[idx_start + len(MARKER):]
    m = re.search(r'\n(?:def |class )', rest)
    if m:
        idx_end = idx_start + len(MARKER) + m.start() + 1
        src = src[:idx_start] + NEW_FUNC + '\n\n' + src[idx_end:]
        print('[+] Replaced: send_release_emails()')
    else:
        print('[!] Could not find end of send_release_emails, skipping')
else:
    # Function might be named differently or absent — append it after imports
    print('[!] send_release_emails not found in file, appending it')
    src += '\n\n' + NEW_FUNC

# ── 3. Append new nominee views ──────────────────────────────────────────────
NEW_VIEWS = '''

# -----------------------------------------------------------------
# NOMINEE OTP VERIFICATION  (public - no login required)
# -----------------------------------------------------------------

def nominee_verify(request, pk):
    """
    Public page where a nominee enters their OTP to verify identity.
    No Django login required - accessed via emailed link.
    """
    nominee = get_object_or_404(Nominee, pk=pk)
    error = None

    if request.method == 'POST':
        entered = request.POST.get('otp', '').strip()
        if nominee.otp and entered == nominee.otp:
            nominee.otp_verified = True
            nominee.save(update_fields=['otp_verified'])
            request.session[f'nominee_verified_{pk}'] = True
            messages.success(request, f'Identity verified! Welcome, {nominee.name}.')
            return redirect('vault:nominee_access', pk=pk)
        else:
            error = 'Invalid OTP. Please check your email and try again.'

    return render(request, 'vault/nominee_verify.html', {
        'nominee': nominee,
        'error': error,
    })


def nominee_access(request, pk):
    """
    Shows the decrypted assets assigned to a verified nominee.
    Requires OTP session key set by nominee_verify.
    """
    nominee = get_object_or_404(Nominee, pk=pk)

    session_ok = request.session.get(f'nominee_verified_{pk}', False)
    if not (nominee.otp_verified and session_ok):
        messages.warning(request, 'Please verify your OTP first.')
        return redirect('vault:nominee_verify', pk=pk)

    raw_assets = DigitalAsset.objects.filter(nominees=nominee)
    asset_data = []
    for asset in raw_assets:
        decrypted = None
        file_url = None
        if asset.document_file:
            file_url = asset.document_file.url
        elif asset.encrypted_data:
            try:
                decrypted = decrypt(asset.encrypted_data)
            except Exception:
                decrypted = '[Could not decrypt content]'
        asset_data.append({
            'asset': asset,
            'decrypted': decrypted,
            'file_url': file_url,
        })

    try:
        final_message = nominee.user.profile.final_message
    except Exception:
        final_message = None

    return render(request, 'vault/nominee_access.html', {
        'nominee': nominee,
        'asset_data': asset_data,
        'final_message': final_message,
    })


# -----------------------------------------------------------------
# TEST: MANUALLY TRIGGER OTP EMAIL SEND (for development testing)
# -----------------------------------------------------------------
@login_required
def test_send_otp(request):
    """
    Manually sends OTP release emails to all nominees without waiting
    for real inactivity. POST only, CSRF protected.
    Used for testing the nominee verification flow.
    """
    if request.method != 'POST':
        return redirect('vault:settings')

    nominees = Nominee.objects.filter(user=request.user)
    if not nominees.exists():
        messages.warning(request, 'Add at least one nominee before testing.')
        return redirect('vault:settings')

    release_req, _ = ReleaseRequest.objects.get_or_create(
        user=request.user,
        status='triggered',
        defaults={
            'triggered_at': timezone.now(),
            'notes': 'Manual test trigger from Settings page.',
        }
    )
    # Force re-send even if previously sent
    release_req.warning_sent_at = None
    release_req.save(update_fields=['warning_sent_at'])

    send_release_emails(request.user, release_req, request=request)

    messages.success(
        request,
        f'Test OTP emails sent to {nominees.count()} nominee(s). '
        f'Check their inboxes - each email has a unique OTP and verification link.'
    )
    log_activity(request.user, 'Manually triggered test OTP release emails from settings')
    return redirect('vault:settings')
'''

if 'def nominee_verify(' not in src:
    src += NEW_VIEWS
    print('[+] Appended: nominee_verify, nominee_access, test_send_otp')
else:
    print('[=] nominee views already present')

# ── Write back as clean UTF-8 (no BOM) ──────────────────────────────────────
with open(VIEWS_PATH, 'w', encoding='utf-8', newline='\n') as f:
    f.write(src)

print('[OK] vault/views.py patched and re-saved as clean UTF-8.')
print(f'     File size: {os.path.getsize(VIEWS_PATH)} bytes')
