from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from accounts.models import UserProfile


def _get_role(user):
    """Return the user's role string, or None if no profile exists."""
    try:
        return user.profile.role
    except (UserProfile.DoesNotExist, AttributeError):
        return None


def _is_privileged(user):
    """
    Returns True if the user has unrestricted access:
      - SYSTEM_OWNER role
      - sales role
      - Django superuser
    """
    if user.is_superuser:
        return True
    role = _get_role(user)
    return role in (UserProfile.SYSTEMOWNER, UserProfile.SALES)


def _requires_admin_login(user):
    """
    Returns True if a non-privileged user also has staff/superuser status,
    granting them access to admin-required areas.
    """
    return user.is_staff or user.is_superuser


def sales_access_required(view_func):
    """
    Allow:  SYSTEM_OWNER, sales role, or superuser.
    Deny:   everyone else → redirect to login with a warning.

    Use this on sales-exclusive views (receipts, reports, etc.) that should
    be accessible ONLY to sales staff and owners.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if _is_privileged(request.user):
            return view_func(request, *args, **kwargs)
        messages.warning(request, 'You do not have permission to access that page.')
        return redirect('dashboard')
    return wrapper


def admin_or_privileged_required(view_func):
    """
    Allow:  SYSTEM_OWNER, sales role, superuser, or staff (admin login).
    Deny:   ordinary non-staff users → 403-style redirect with warning.

    Use this on views that require at minimum an admin login for non-sales roles.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if _is_privileged(request.user) or _requires_admin_login(request.user):
            return view_func(request, *args, **kwargs)
        messages.warning(
            request,
            'Access denied. Only Sales staff or users with admin privileges can access this page.'
        )
        return redirect('dashboard')
    return wrapper
