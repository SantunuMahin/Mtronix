from rest_framework.permissions import BasePermission, SAFE_METHODS

from accounts.decorators import (
    INVENTORY_WRITE_ROLES,
    MANAGEMENT_ROLES,
    SALES_ROLES,
    has_any_role,
)


class _BaseRolePermission(BasePermission):
    read_roles = ()
    write_roles = ()

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return not self.read_roles or has_any_role(request.user, self.read_roles)
        return has_any_role(request.user, self.write_roles)


class ManagementWritePermission(_BaseRolePermission):
    """Any authenticated user can read; only management (Owner/Admin/Manager) can write."""
    read_roles = ()
    write_roles = MANAGEMENT_ROLES


class SalesRolePermission(_BaseRolePermission):
    """Sales, Manager, Admin, System Owner can read and create sales."""
    read_roles = SALES_ROLES
    write_roles = SALES_ROLES


class InventoryWritePermission(_BaseRolePermission):
    """Storekeeper, Manager, Admin, System Owner can read and create purchases/suppliers."""
    read_roles = INVENTORY_WRITE_ROLES
    write_roles = INVENTORY_WRITE_ROLES
