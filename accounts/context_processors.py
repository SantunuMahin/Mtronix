from accounts.models import UserProfile


def rbac_flags(request):
    """
    Injects role-based access flags into every template context.

    Flags:
        rbac_is_privileged  – True for SYSTEM_OWNER, sales role, or superuser.
                              These users can access every section including sales.
        rbac_can_access     – True for privileged users OR staff users (admin login).
                              These users can access products/inventory/suppliers/purchases.
    """
    if not request.user.is_authenticated:
        return {
            'rbac_is_privileged': False,
            'rbac_can_access': False,
        }

    is_superuser = request.user.is_superuser
    is_staff = request.user.is_staff

    role = None
    try:
        role = request.user.profile.role
    except (UserProfile.DoesNotExist, AttributeError):
        pass

    is_privileged = is_superuser or role in (UserProfile.SYSTEMOWNER, UserProfile.SALES)
    can_access = is_privileged or is_staff

    return {
        'rbac_is_privileged': is_privileged,
        'rbac_can_access': can_access,
    }
