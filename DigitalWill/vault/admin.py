"""
Admin registrations for the vault app.
All models are registered so they can be managed via /admin/
"""

from django.contrib import admin
from .models import UserProfile, DigitalAsset, Nominee, AssetAccess, ActivityLog, ReleaseRequest


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'inactivity_days', 'last_activity']
    list_filter  = ['inactivity_days']


@admin.register(DigitalAsset)
class DigitalAssetAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'category', 'created_at']
    list_filter  = ['category']
    search_fields = ['title', 'user__username']


@admin.register(Nominee)
class NomineeAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'user', 'otp_verified', 'created_at']
    list_filter  = ['otp_verified']


@admin.register(AssetAccess)
class AssetAccessAdmin(admin.ModelAdmin):
    list_display = ['asset', 'nominee']


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display  = ['user', 'action', 'timestamp']
    list_filter   = ['user']
    readonly_fields = ['user', 'action', 'timestamp']


@admin.register(ReleaseRequest)
class ReleaseRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'status', 'triggered_at', 'warning_sent_at']
    list_filter  = ['status']
