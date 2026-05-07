"""
Run this ONCE from the project root to patch vault/views.py:
    python _add_otp_views.py

It will:
  1. Replace send_release_emails() with the OTP-enabled version
  2. Append nominee_verify, nominee_access, test_send_otp views
"""
import re, os

VIEWS = os.path.join(os.path.dirname(__file__), 'vault', 'views.py')

with open(VIEWS, 'r', encoding='utf-8') as f:
    src = f.read()

# ── 1. Add `import random` if missing ───────────────────────────────────────
if 'import random' not in src:
    src = src.replace(
        'from django.core.mail import send_mail',
        'import random\nfrom django.core.mail import send_mail',
        1,
    )
    print('[+] Added: import random')

# ── 2. Replace send_release_emails() ────────────────────────────────────────
OLD_FUNC_START = 'def send_release_emails('
NEW_FUNC = '''def send_release_emails(user, release_request, request=None):
    """
    Send personalised OTP release emails to every nominee of `user`.

    For each nominee:
      1. Generate a fresh 6-digit OTP and save it to nominee.otp
      2. Build a verification URL  (/access/verify/<nominee_pk>/)
      3. Email the OTP + link so the nominee can verify and view assets

    Errors are caught and logged so they never crash the caller.
    Called exactly once per release event (guarded by warning_sent_at).
    """
    nominees = Nominee.objects.filter(user=user)
    if not nominees.exists():
        log_activity(user, 'Release triggered but no nominees configured — no emails sent.')
        return

    base_url = (
        f"{request.scheme}://{request.get_host()}" if request
        else 'http://127.0.0.1:8000'
    )

    sent_count = 0
    for nominee in nominees:
        # ── Generate & save a fresh OTP ──────────────────────────────
        otp = str(random.randint(100000, 999999))
        nominee.otp          = otp
        nominee.otp_verified = False
        nominee.save(update_fields=['otp', 'otp_verified'])

        verify_url = f"{base_url}/access/verify/{nominee.pk}/"

        # ── Collect assigned assets ───────────────────────────────────
        assigned_assets = DigitalAsset.objects.filter(user=user, nominees=nominee)
        asset_lines = (
            "\\n".join(f"  • {a.title}  [{a.get_category_display()}]" for a in assigned_assets)
            if assigned_assets.exists()
            else "  (All assets of the account holder)"
        )

        owner = user.get_full_name() or user.username
        subject = f"[Digital Will] Access granted by {owner} — Your OTP inside"
        body = (
            f"Dear {nominee.name},\\n\\n"
            f"This is an automated notification from Digital Will Platform.\\n\\n"
            f"{'='*54}\\n"
            f"  {owner} has been inactive for an extended period.\\n"
            f"  You have been designated as a trusted nominee.\\n"
            f"{'='*54}\\n\\n"
            f"ASSETS YOU CAN ACCESS:\\n{asset_lines}\\n\\n"
            f"{'-'*54}\\n"
            f"  YOUR ONE-TIME PASSWORD (OTP): {otp}\\n"
            f"{'-'*54}\\n\\n"
            f"To view the assets, visit this link and enter your OTP:\\n"
            f"  {verify_url}\\n\\n"
            f"This OTP is unique to you. Do not share it.\\n\\n"
            f"Release Request #: {release_request.pk}\\n"
            f"Triggered on     : {timezone.now().strftime('%d %B %Y at %H:%M IST')}\\n\\n"
            f"— Digital Will Platform\\n"
            f"This is an automated message. Please do not reply."
        )

        try:
            send_mail(
                subject        = subject,
                message        = body,
                from_email     = settings.DEFAULT_FROM_EMAIL,
                recipient_list = [nominee.email],
                fail_silently  = False,
            )
            sent_count += 1
            log_activity(user, f'OTP release email sent to {nominee.name} <{nominee.email}>')
        except Exception as exc:
            log_activity(user, f'Failed to send release email to {nominee.email}: {exc}')

    # Mark dispatched so we don't re-send on next dashboard load
    release_request.warning_sent_at = timezone.now()
    release_request.notes = (
        f'{release_request.notes or ""} '
        f'| OTP emails sent to {sent_count}/{nominees.count()} nominee(s) '
        f'on {timezone.now().strftime("%d %b %Y %H:%M IST")}.'
    ).strip()
    release_request.save(update_fields=['warning_sent_at', 'notes'])

'''

# Find start of old function and next def at same indent level
if OLD_FUNC_START in src:
    # Find the old function block (from def to next blank-line-then-def)
    idx = src.index(OLD_FUNC_START)
    # Find the end: next "def " at column 0 after idx
    next_def = re.search(r'\ndef [a-z]', src[idx+10:])
    if next_def:
        end_idx = idx + 10 + next_def.start() + 1  # keep the \n before next def
        src = src[:idx] + NEW_FUNC + '\n' + src[end_idx:]
        print('[+] Replaced: send_release_emails()')
    else:
        print('[!] Could not find end of send_release_emails — appending instead')
        src += '\n' + NEW_FUNC
else:
    print('[!] send_release_emails not found — appending')
    src += '\n' + NEW_FUNC

# ── 3. Append new views if not already present ───────────────────────────────
NEW_VIEWS = '''

# ─────────────────────────────────────────────────────────
# NOMINEE OTP VERIFICATION  (public — no login required)
# ─────────────────────────────────────────────────────────

def nominee_verify(request, pk):
    """
    Public page where a nominee enters their OTP to verify identity.
    No login required — this is accessed from the email link.
    """
    nominee = get_object_or_404(Nominee, pk=pk)
    error   = None

    if request.method == 'POST':
        entered = request.POST.get('otp', '').strip()
        if nominee.otp and entered == nominee.otp:
            nominee.otp_verified = True
            nominee.save(update_fields=['otp_verified'])
            # Store in session so access page is unlocked
            request.session[f'nominee_verified_{pk}'] = True
            messages.success(request, f'Identity verified! Welcome, {nominee.name}.')
            return redirect('vault:nominee_access', pk=pk)
        else:
            error = 'Invalid OTP. Please check your email and try again.'

    return render(request, 'vault/nominee_verify.html', {
        'nominee': nominee,
        'error':   error,
    })


def nominee_access(request, pk):
    """
    Shows the decrypted assets assigned to a verified nominee.
    Requires OTP verification (checked via session flag or otp_verified field).
    """
    nominee = get_object_or_404(Nominee, pk=pk)

    # Security: must be OTP-verified
    session_verified = request.session.get(f'nominee_verified_{pk}', False)
    if not (nominee.otp_verified and session_verified):
        messages.warning(request, 'Please verify your OTP first.')
        return redirect('vault:nominee_verify', pk=pk)

    # Collect assets assigned to this nominee
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
                decrypted = '[Could not decrypt content]'
        asset_data.append({
            'asset':     asset,
            'decrypted': decrypted,
            'file_url':  file_url,
        })

    # Also retrieve the owner's final message
    try:
        owner_profile = nominee.user.profile
        final_message = owner_profile.final_message
    except Exception:
        final_message = None

    return render(request, 'vault/nominee_access.html', {
        'nominee':       nominee,
        'asset_data':    asset_data,
        'final_message': final_message,
    })


# ─────────────────────────────────────────────────────────
# TEST: MANUALLY TRIGGER OTP EMAIL SEND
# Allows the user to test the flow without waiting for inactivity
# ─────────────────────────────────────────────────────────
@login_required
def test_send_otp(request):
    """
    Manually trigger release emails (with fresh OTPs) to all nominees.
    Used ONLY for testing — creates a temporary 'triggered' ReleaseRequest.
    POST only, CSRF protected.
    """
    if request.method != 'POST':
        return redirect('vault:settings')

    nominees = Nominee.objects.filter(user=request.user)
    if not nominees.exists():
        messages.warning(request, 'Add at least one nominee before testing.')
        return redirect('vault:settings')

    # Get or create a test release request
    release_req, created = ReleaseRequest.objects.get_or_create(
        user   = request.user,
        status = 'triggered',
        defaults={
            'triggered_at': timezone.now(),
            'notes':        'Manual test trigger from Settings.',
        }
    )
    # Reset warning_sent_at so emails fire even if previously sent
    release_req.warning_sent_at = None
    release_req.save(update_fields=['warning_sent_at'])

    send_release_emails(request.user, release_req, request=request)

    messages.success(
        request,
        f'✅ OTP emails sent to {nominees.count()} nominee(s). '
        f'Check their inboxes — each email contains a unique OTP and verification link.'
    )
    log_activity(request.user, 'Manually triggered test OTP release emails')
    return redirect('vault:settings')
'''

if 'def nominee_verify(' not in src:
    src += NEW_VIEWS
    print('[+] Appended: nominee_verify, nominee_access, test_send_otp views')
else:
    print('[=] Views already present, skipping append')

# ── Save ─────────────────────────────────────────────────────────────────────
with open(VIEWS, 'w', encoding='utf-8') as f:
    f.write(src)

print('[✓] vault/views.py patched successfully.')
