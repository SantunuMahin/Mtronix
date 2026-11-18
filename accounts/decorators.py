from functools import wraps

from django.http import JsonResponse
from django.shortcuts import redirect, render

from accounts.models import UserProfile


def _get_role(user):
    """Return the user's role string, or None if no profile exists."""
    try:
        return user.profile.role
    except (UserProfile.DoesNotExist, AttributeError):
        return None


def _is_json_request(request):
    """Return True if the request expects a JSON response."""
    return (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
        or request.path_info.startswith('/sales/barcode-lookup/')
        or request.path_info.startswith('/sales/customer-lookup/')
        or request.path_info.startswith('/products/api/')
    )


def has_any_role(user, allowed_roles):
    """Return True if user is superuser or has one of allowed_roles."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return _get_role(user) in allowed_roles


def role_required(*allowed_roles):
    """
    Restrict view access to superusers or users whose UserProfile.role
    is in allowed_roles. Renders 403.html with HTTP 403 on denial.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if _is_json_request(request):
                    return JsonResponse({'success': False, 'error': 'Authentication required.'}, status=401)
                return redirect('accounts:login')
            if has_any_role(request.user, allowed_roles):
                return view_func(request, *args, **kwargs)
            if _is_json_request(request):
                return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
            return render(request, '403.html', status=403)
        return wrapper
    return decorator


ADMIN_ROLES = (UserProfile.SYSTEMOWNER, UserProfile.ADMIN)
MANAGEMENT_ROLES = (UserProfile.SYSTEMOWNER, UserProfile.ADMIN, UserProfile.MANAGER)
SALES_ROLES = (UserProfile.SYSTEMOWNER, UserProfile.ADMIN, UserProfile.MANAGER, UserProfile.SALES)
INVENTORY_WRITE_ROLES = (UserProfile.SYSTEMOWNER, UserProfile.ADMIN, UserProfile.MANAGER, UserProfile.STOREKEEPER)

admin_required = role_required(*ADMIN_ROLES)
management_required = role_required(*MANAGEMENT_ROLES)
sales_access_required = role_required(*SALES_ROLES)
inventory_write_required = role_required(*INVENTORY_WRITE_ROLES)
admin_or_privileged_required = management_required
