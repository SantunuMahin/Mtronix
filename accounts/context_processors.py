from accounts.decorators import (
    ADMIN_ROLES,
    INVENTORY_WRITE_ROLES,
    MANAGEMENT_ROLES,
    SALES_ROLES,
    has_any_role,
)


def rbac_flags(request):
    """
    Injects role-based access flags into every template context.

    Flags:
        rbac_is_admin         – SYSTEM_OWNER, ADMIN, or superuser.
        rbac_is_management    – SYSTEM_OWNER, ADMIN, MANAGER, or superuser.
        rbac_can_access_sales – SYSTEM_OWNER, ADMIN, MANAGER, SALES, or superuser.
        rbac_can_manage_stock – SYSTEM_OWNER, ADMIN, MANAGER, STOREKEEPER, or superuser.
        rbac_is_privileged    – Alias for rbac_can_access_sales.
        rbac_can_access       – Alias for rbac_can_manage_stock.
    """
    user = request.user
    if not user.is_authenticated:
        return {
            'rbac_is_admin': False,
            'rbac_is_management': False,
            'rbac_can_access_sales': False,
            'rbac_can_manage_stock': False,
            'rbac_is_privileged': False,
            'rbac_can_access': False,
        }

    is_admin = has_any_role(user, ADMIN_ROLES)
    is_management = has_any_role(user, MANAGEMENT_ROLES)
    can_access_sales = has_any_role(user, SALES_ROLES)
    can_manage_stock = has_any_role(user, INVENTORY_WRITE_ROLES)

    return {
        'rbac_is_admin': is_admin,
        'rbac_is_management': is_management,
        'rbac_can_access_sales': can_access_sales,
        'rbac_can_manage_stock': can_manage_stock,
        'rbac_is_privileged': can_access_sales,
        'rbac_can_access': can_manage_stock,
    }
