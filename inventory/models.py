from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from products.models import Product


class Inventory(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='inventory')
    quantity = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'inventory'

    def __str__(self):
        return f'{self.product.name}: {self.quantity}'


class StockMovement(models.Model):
    MOVEMENT_ADD = 'ADD'
    MOVEMENT_REMOVE = 'REMOVE'
    MOVEMENT_CORRECTION = 'CORRECTION'
    MOVEMENT_SALE = 'SALE'
    MOVEMENT_PURCHASE = 'PURCHASE'

    MOVEMENT_TYPE_CHOICES = [
        (MOVEMENT_ADD, 'Stock In (Addition)'),
        (MOVEMENT_REMOVE, 'Stock Out (Reduction)'),
        (MOVEMENT_CORRECTION, 'Inventory Count Correction'),
        (MOVEMENT_SALE, 'POS Sale Deduction'),
        (MOVEMENT_PURCHASE, 'Supplier Purchase Inflow'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPE_CHOICES, default=MOVEMENT_ADD)
    quantity = models.IntegerField(help_text='Positive for additions/purchases, negative or delta for removals')
    previous_quantity = models.PositiveIntegerField(default=0)
    new_quantity = models.PositiveIntegerField(default=0)
    reason = models.CharField(max_length=255, default='Manual adjustment')
    notes = models.TextField(blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'stock movement'
        verbose_name_plural = 'stock movements'

    def __str__(self):
        return f'{self.product.name} | {self.get_movement_type_display()} ({self.quantity:+d})'

