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
    def create_sale(*, customer_name='', customer_phone='', customer_address='', payment_status='PAID', paid_amount=0, items):
        from decimal import Decimal
        if not items:
            raise ValueError('A sale must contain at least one item')

        sale = Sale.objects.create(
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_address=customer_address,
            payment_status=payment_status,
            paid_amount=Decimal(str(paid_amount or 0)),
        )
        for item_data in items:
            product = item_data.get('product')
            quantity = item_data['quantity']
            if product:
                InventoryService.remove_stock(product, quantity)
            SaleItem.objects.create(sale=sale, **item_data)

        # Synchronize paid_amount based on payment status and total
        tot = sale.total_amount
        if sale.payment_status == 'PAID':
            sale.paid_amount = tot
            sale.save(update_fields=['paid_amount'])
        elif sale.payment_status == 'UNPAID':
            sale.paid_amount = Decimal('0.00')
            sale.save(update_fields=['paid_amount'])
        elif sale.payment_status == 'PARTIAL':
            p_val = Decimal(str(paid_amount or 0))
            if p_val >= tot and tot > 0:
                sale.payment_status = 'PAID'
                sale.paid_amount = tot
            elif p_val <= 0:
                sale.payment_status = 'UNPAID'
                sale.paid_amount = Decimal('0.00')
            else:
                sale.paid_amount = p_val
            sale.save(update_fields=['payment_status', 'paid_amount'])

        return sale
