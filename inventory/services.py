from django.db import transaction
from django.db.models import F

from inventory.models import Inventory


class InventoryService:
    @staticmethod
    @transaction.atomic
    def ensure_inventory(product):
        inventory, _ = Inventory.objects.select_for_update().get_or_create(
            product=product,
            defaults={'quantity': 0},
        )
        return inventory

    @staticmethod
    @transaction.atomic
    def add_stock(product, qty):
        if qty <= 0:
            raise ValueError('Quantity must be greater than zero')

        InventoryService.ensure_inventory(product)
        Inventory.objects.filter(product=product).update(quantity=F('quantity') + qty)
        return Inventory.objects.get(product=product)

    @staticmethod
    @transaction.atomic
    def remove_stock(product, qty):
        if qty <= 0:
            raise ValueError('Quantity must be greater than zero')

        inventory = InventoryService.ensure_inventory(product)
        if inventory.quantity < qty:
            raise ValueError('Out of stock')

        Inventory.objects.filter(product=product).update(quantity=F('quantity') - qty)
        return Inventory.objects.get(product=product)
