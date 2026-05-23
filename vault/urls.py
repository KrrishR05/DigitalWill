"""
URL patterns for the vault app.

Structure:
  /                    → Home page (landing)
  /auth/register/      → User registration
  /auth/login/         → Login
  /auth/logout/        → Logout
  /dashboard/          → User dashboard
  /assets/             → List digital assets
  /assets/add/         → Add new asset
  /assets/<id>/        → View single asset (decrypted)
  /assets/<id>/edit/   → Edit asset
  /assets/<id>/delete/ → Delete asset
  /nominees/           → List nominees
  /nominees/add/       → Add nominee
  /nominees/<id>/delete/ → Remove nominee
  /activity/           → Activity log
  /settings/           → User settings (inactivity threshold, final message)
"""

from django.urls import path
from . import views
from . import otp_views

app_name = 'vault'

urlpatterns = [
    # ── Home ──────────────────────────────────────
    path('', views.home, name='home'),

    # ── Authentication ─────────────────────────────
    path('auth/register/',        views.register_view,   name='register'),
    path('auth/login/',           views.login_view,      name='login'),
    path('auth/logout/',          views.logout_view,     name='logout'),
    path('auth/delete-account/',  views.delete_account,  name='delete_account'),

    # ── Dashboard ──────────────────────────────────
    path('dashboard/', views.dashboard, name='dashboard'),

    # ── Digital Assets ─────────────────────────────
    path('assets/',             views.asset_list,   name='asset_list'),
    path('assets/add/',         views.asset_add,    name='asset_add'),
    path('assets/<int:pk>/',    views.asset_detail, name='asset_detail'),
    path('assets/<int:pk>/edit/',   views.asset_edit,   name='asset_edit'),
    path('assets/<int:pk>/delete/', views.asset_delete, name='asset_delete'),

    # ── Nominees ──────────────────────────────────
    path('nominees/',                    views.nominee_list,   name='nominee_list'),
    path('nominees/add/',                views.nominee_add,    name='nominee_add'),
    path('nominees/<int:pk>/delete/',    views.nominee_delete, name='nominee_delete'),
    path('nominees/<int:pk>/assign/',    views.nominee_assign, name='nominee_assign'),

    # ── Activity Log ──────────────────────────────
    path('activity/', views.activity_log, name='activity_log'),

    # ── Settings ─────────────────────────────────
    path('settings/',          views.settings_view,       name='settings'),
    path('settings/test-otp/', otp_views.test_send_otp,   name='test_send_otp'),

    # ── Nominee OTP Verification (public — no login needed) ──
    path('access/verify/<int:pk>/', otp_views.nominee_verify, name='nominee_verify'),
    path('access/<int:pk>/',        otp_views.nominee_access,  name='nominee_access'),
]
