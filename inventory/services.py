from decimal import Decimal
from django.db import transaction
from django.db.models import F

from inventory.models import Inventory, StockMovement
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
    def add_stock(product, qty, user=None, reason='Manual Restock / Inflow', notes='', movement_type=StockMovement.MOVEMENT_ADD):
        if qty <= 0:
            raise ValueError('Quantity must be greater than zero')

        inventory = InventoryService.ensure_inventory(product)
        prev_qty = inventory.quantity
        new_qty = prev_qty + qty

        Inventory.objects.filter(product=product).update(quantity=new_qty)
        inventory.refresh_from_db()

        StockMovement.objects.create(
            product=product,
            movement_type=movement_type,
            quantity=qty,
            previous_quantity=prev_qty,
            new_quantity=new_qty,
            reason=reason or 'Manual Restock / Inflow',
            notes=notes or '',
            user=user,
        )
        return inventory

    @staticmethod
    @transaction.atomic
    def remove_stock(product, qty, user=None, reason='Manual Removal / Defect', notes='', movement_type=StockMovement.MOVEMENT_REMOVE):
        if qty <= 0:
            raise ValueError('Quantity must be greater than zero')

        inventory = InventoryService.ensure_inventory(product)
        prev_qty = inventory.quantity
        if prev_qty < qty:
            raise ValueError(f'Out of stock. Requested: {qty}, Available: {prev_qty}')

        new_qty = prev_qty - qty
        Inventory.objects.filter(product=product).update(quantity=new_qty)
        inventory.refresh_from_db()

        StockMovement.objects.create(
            product=product,
            movement_type=movement_type,
            quantity=-qty,
            previous_quantity=prev_qty,
            new_quantity=new_qty,
            reason=reason or 'Manual Removal / Defect',
            notes=notes or '',
            user=user,
        )
        return inventory

    @staticmethod
    @transaction.atomic
    def set_stock(product, new_qty, user=None, reason='Inventory Count Correction', notes=''):
        if new_qty < 0:
            raise ValueError('Quantity cannot be negative')

        inventory = InventoryService.ensure_inventory(product)
        prev_qty = inventory.quantity
        delta = new_qty - prev_qty

        Inventory.objects.filter(product=product).update(quantity=new_qty)
        inventory.refresh_from_db()

        StockMovement.objects.create(
            product=product,
            movement_type=StockMovement.MOVEMENT_CORRECTION,
            quantity=delta,
            previous_quantity=prev_qty,
            new_quantity=new_qty,
            reason=reason or 'Inventory Count Correction',
            notes=notes or '',
            user=user,
        )
        return inventory

    @staticmethod
    @transaction.atomic
    def create_purchase(*, supplier, product, quantity, unit_price, user=None):
        purchase = Purchase.objects.create(
            supplier=supplier,
            product=product,
            quantity=quantity,
            unit_price=unit_price,
        )
        supplier_name = supplier.name if supplier else 'Supplier'
        InventoryService.add_stock(
            product=product,
            qty=quantity,
            user=user,
            reason=f'Purchase from {supplier_name}',
            movement_type=StockMovement.MOVEMENT_PURCHASE,
        )
        return purchase

    @staticmethod
    @transaction.atomic
    def create_sale(*, customer_name='', customer_phone='', customer_address='', payment_status='PAID', paid_amount=0, items, user=None):
        if not items:
            raise ValueError('A sale must contain at least one item')

        sale = Sale.objects.create(
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_address=customer_address,
            payment_status=payment_status,
            paid_amount=Decimal(str(paid_amount or 0)),
        )
        cust_label = customer_name or 'Walk-in Customer'
        for item_data in items:
            product = item_data.get('product')
            quantity = item_data['quantity']
            if product:
                InventoryService.remove_stock(
                    product=product,
                    qty=quantity,
                    user=user,
                    reason=f'Sale #{sale.pk:05d} to {cust_label}',
                    movement_type=StockMovement.MOVEMENT_SALE,
                )
            SaleItem.objects.create(sale=sale, **item_data)

        # Synchronize paid_amount based on payment status and fresh total
        sale.refresh_from_db()
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
