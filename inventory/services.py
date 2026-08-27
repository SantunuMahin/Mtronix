from django.db import transaction
from django.db.models import F

from inventory.models import Inventory
from purchases.models import Purchase
from sales.models import Sale, SaleItem


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

    @staticmethod
    @transaction.atomic
    def create_purchase(*, supplier, product, quantity, unit_price):
        purchase = Purchase.objects.create(
            supplier=supplier,
            product=product,
            quantity=quantity,
            unit_price=unit_price,
        )
        InventoryService.add_stock(product, quantity)
        return purchase

    @staticmethod
    @transaction.atomic
    def create_sale(*, customer_name='', items):
        if not items:
            raise ValueError('A sale must contain at least one item')

        sale = Sale.objects.create(customer_name=customer_name)
        for item_data in items:
            product = item_data['product']
            quantity = item_data['quantity']
            InventoryService.remove_stock(product, quantity)
            SaleItem.objects.create(sale=sale, **item_data)
        return sale
