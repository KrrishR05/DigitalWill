"""
Forms for the vault app.

Forms defined:
  - RegisterForm    → New user registration
  - LoginForm       → User login
  - AssetForm       → Create/Edit a digital asset
  - NomineeForm     → Add a nominee
  - SettingsForm    → Update inactivity threshold and final message
"""

import re

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from .models import DigitalAsset, Nominee, UserProfile


# ─────────────────────────────────────────────────────────
# REGISTER FORM
# ─────────────────────────────────────────────────────────
class RegisterForm(forms.Form):
    username   = forms.CharField(max_length=150, label='Username')
    email      = forms.EmailField(label='Email Address')
    password1  = forms.CharField(widget=forms.PasswordInput, label='Password')
    password2  = forms.CharField(widget=forms.PasswordInput, label='Confirm Password')

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            return email
        # Enforce Gmail-only (backend security guard)
        if not re.match(r'^[a-zA-Z0-9._%+\-]+@gmail\.com$', email, re.IGNORECASE):
            raise forms.ValidationError(
                "Please enter a valid Gmail address (e.g. you@gmail.com)."
            )
        # Check uniqueness
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned


# ─────────────────────────────────────────────────────────
# LOGIN FORM
# ─────────────────────────────────────────────────────────
class LoginForm(forms.Form):
    # Single field accepts both username and email — detection is done in the view
    identifier = forms.CharField(
        max_length  = 254,
        label       = 'Username or Email',
        widget      = forms.TextInput(attrs={'autocomplete': 'username'}),
    )
    password = forms.CharField(widget=forms.PasswordInput, label='Password')


# ─────────────────────────────────────────────────────────
# ASSET FORM
# Category 'document' can upload a file OR type content.
# Other categories must type content (always encrypted).
# ─────────────────────────────────────────────────────────
class AssetForm(forms.ModelForm):
    # Content field — required for password/note, optional for document
    encrypted_data = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5, 'placeholder': 'Enter your sensitive content here...'}),
        label='Content (will be encrypted)',
        required=False,   # Validated in view based on category
    )

    # File upload — only shown/used when category is 'document'
    document_file = forms.FileField(
        required=False,
        label='Upload File',
        widget=forms.ClearableFileInput(attrs={'accept': '*/*'}),
    )

    # Nominees who can access this asset — queryset is set per-user in the view
    # so users only see their own nominees in the selector
    nominees = forms.ModelMultipleChoiceField(
        queryset=Nominee.objects.none(),  # overridden in view
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Assign Nominees',
        help_text='Select nominees who will receive access to this asset.',
    )

    class Meta:
        model  = DigitalAsset
        fields = ['title', 'category', 'encrypted_data', 'document_file', 'nominees']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Gmail Password, Bank Document...'}),
        }

    def clean(self):
        cleaned = super().clean()
        category       = cleaned.get('category')
        content        = cleaned.get('encrypted_data')
        document_file  = cleaned.get('document_file')

        if category == 'document':
            # Document: must have EITHER a file OR text content
            if not document_file and not content:
                raise forms.ValidationError(
                    'For documents, please upload a file or type content.'
                )
        else:
            # Password / Note: must have text content
            if not content:
                raise forms.ValidationError('Please enter the content to encrypt.')
        return cleaned


# ─────────────────────────────────────────────────────────
# NOMINEE FORM
# ─────────────────────────────────────────────────────────
class NomineeForm(forms.ModelForm):
    class Meta:
        model  = Nominee
        fields = ['name', 'email']
        widgets = {
            'name':  forms.TextInput(attrs={'placeholder': 'Full Name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'email@example.com'}),
        }


# ─────────────────────────────────────────────────────────
# SETTINGS FORM
# ─────────────────────────────────────────────────────────
INACTIVITY_CHOICES = [
    (7,   '7 days'),
    (14,  '14 days'),
    (30,  '30 days (recommended)'),
    (60,  '60 days'),
    (90,  '90 days'),
    (180, '180 days'),
    (365, '365 days'),
]

class SettingsForm(forms.ModelForm):
    inactivity_days = forms.TypedChoiceField(
        choices   = INACTIVITY_CHOICES,
        coerce    = int,
        label     = 'Inactivity Threshold',
        help_text = 'If you are inactive beyond this period, nominees will be notified.',
        widget    = forms.Select(),
    )
    final_message = forms.CharField(
        required  = False,
        label     = 'Final Message to Nominees',
        help_text = 'A personal farewell message delivered to your nominees on release.',
        widget    = forms.Textarea(attrs={
            'rows': 7,
            'placeholder': 'Write your final message to your loved ones\u2026',
        }),
    )

    class Meta:
        model  = UserProfile
        fields = ['inactivity_days', 'final_message']


# ─────────────────────────────────────────────────────────
# ACCOUNT INFO FORM  (update display name + email)
# ─────────────────────────────────────────────────────────
class AccountInfoForm(forms.ModelForm):
    class Meta:
        model  = User
        fields = ['first_name', 'last_name', 'email']
        labels = {
            'first_name': 'First Name',
            'last_name':  'Last Name',
            'email':      'Email Address',
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'John'}),
            'last_name':  forms.TextInput(attrs={'placeholder': 'Smith'}),
            'email':      forms.EmailInput(attrs={'placeholder': 'john@example.com'}),
        }


# ─────────────────────────────────────────────────────────
# PASSWORD CHANGE FORM  (re-export Django's built-in)
# ─────────────────────────────────────────────────────────
PasswordChangeForm = DjangoPasswordChangeForm
