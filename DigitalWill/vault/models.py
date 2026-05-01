"""
Models for the Digital Will / Vault app.

Models defined here:
  1. UserProfile  — extends Django's User with inactivity settings & final message
  2. DigitalAsset — encrypted storage for passwords, documents, notes
  3. Nominee      — trusted person who receives access after inactivity
  4. AssetAccess  — links which nominees can access which assets
  5. ActivityLog  — audit trail of all important actions
  6. ReleaseRequest — tracks the release workflow state
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# ─────────────────────────────────────────────────────────
# 1. USER PROFILE
# Extends the built-in Django User with Digital Will fields
# ─────────────────────────────────────────────────────────
class UserProfile(models.Model):
    # One-to-one link to Django's User
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # How many days of inactivity before the release workflow triggers
    inactivity_days = models.PositiveIntegerField(default=30)

    # Updated every time the user makes any request (via middleware)
    last_activity = models.DateTimeField(default=timezone.now)

    # A farewell message delivered to nominees on release
    final_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def is_at_risk(self):
        """Returns True if user has been inactive beyond their threshold."""
        from datetime import timedelta
        deadline = self.last_activity + timedelta(days=self.inactivity_days)
        return timezone.now() >= deadline

    def days_since_active(self):
        """Returns number of days since last activity."""
        delta = timezone.now() - self.last_activity
        return delta.days


# ─────────────────────────────────────────────────────────
# 2. DIGITAL ASSET
# Encrypted storage for sensitive data
# ─────────────────────────────────────────────────────────
class DigitalAsset(models.Model):
    CATEGORY_CHOICES = [
        ('password', '🔑 Password'),
        ('document', '📄 Document'),
        ('note',     '📝 Personal Note'),
    ]

    user     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assets')
    title    = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='note')

    # Content is stored ENCRYPTED — never store plaintext here
    # For document-type assets: may be empty if a file is uploaded instead
    encrypted_data = models.TextField(blank=True)

    # File upload — only used when category == 'document'
    document_file = models.FileField(
        upload_to='documents/',
        blank=True,
        null=True,
        help_text='Upload any file type for document assets',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Nominees who will receive access to this asset during release
    # blank=True means an asset can exist without any nominees assigned
    nominees = models.ManyToManyField(
        'Nominee',
        blank=True,
        related_name='assigned_assets',
        help_text='Nominees who can access this asset after inactivity trigger',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_category_display()}] {self.title}"


# ─────────────────────────────────────────────────────────
# 3. NOMINEE
# A trusted person who will receive access to assets
# ─────────────────────────────────────────────────────────
class Nominee(models.Model):
    user  = models.ForeignKey(User, on_delete=models.CASCADE, related_name='nominees')
    name  = models.CharField(max_length=150)
    email = models.EmailField()

    # OTP for nominee identity verification during release
    otp          = models.CharField(max_length=6, blank=True, null=True)
    otp_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} <{self.email}>"


# ─────────────────────────────────────────────────────────
# 4. ASSET ACCESS
# Maps which nominees can see which assets (many-to-many via explicit model)
# ─────────────────────────────────────────────────────────
class AssetAccess(models.Model):
    asset   = models.ForeignKey(DigitalAsset, on_delete=models.CASCADE, related_name='accesses')
    nominee = models.ForeignKey(Nominee,      on_delete=models.CASCADE, related_name='accesses')

    class Meta:
        unique_together = ('asset', 'nominee')  # Prevent duplicate assignments

    def __str__(self):
        return f"{self.nominee.name} → {self.asset.title}"


# ─────────────────────────────────────────────────────────
# 5. ACTIVITY LOG
# Audit trail — every important action is recorded
# ─────────────────────────────────────────────────────────
class ActivityLog(models.Model):
    user      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs')
    action    = models.CharField(max_length=300)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} | {self.action} | {self.timestamp:%Y-%m-%d %H:%M}"


# ─────────────────────────────────────────────────────────
# 6. RELEASE REQUEST
# Tracks the inactivity → release workflow state machine.
#
# Status lifecycle:
#   pending   → user detected inactive, request created
#   triggered → threshold exceeded, nominees would be notified
#   completed → nominees verified and accessed assets
# ─────────────────────────────────────────────────────────
class ReleaseRequest(models.Model):
    STATUS_CHOICES = [
        ('pending',   'Pending'),    # Inactivity detected, request created
        ('triggered', 'Triggered'),  # Threshold exceeded — release workflow fired
        ('completed', 'Completed'),  # Nominees verified and accessed assets
    ]

    user   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='release_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Set to None initially; populated when status is moved to 'triggered'
    triggered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when the release workflow was actually triggered'
    )
    # Set when nominee release emails have been successfully dispatched
    warning_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when nominee notification emails were sent'
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    # Optional notes — e.g. email count, admin remarks, etc.
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-id']   # newest first; triggered_at may be null so sort by id

    def __str__(self):
        return f"Release for {self.user.username} — {self.status}"
