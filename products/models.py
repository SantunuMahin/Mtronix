from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class ProductGroup(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'product group'
        verbose_name_plural = 'product groups'

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200)
    group = models.ForeignKey(
        ProductGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
    )
    sku = models.CharField(max_length=50, unique=True, null=True, blank=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), blank=True, validators=[MinValueValidator(0)])
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    low_stock_threshold = models.PositiveIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_stock(self):
        return self.inventory.quantity if hasattr(self, 'inventory') else 0

    def clean(self):
        super().clean()
        if self.sku:
            self.sku = self.sku.strip() or None
        else:
            self.sku = None

    def save(self, *args, **kwargs):
        if self.sku:
            self.sku = self.sku.strip() or None
        else:
            self.sku = None
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            from inventory.models import Inventory
            Inventory.objects.get_or_create(product=self, defaults={'quantity': 0})

    def __str__(self):
        if self.sku:
            return f'{self.name} ({self.sku})'
        return self.name
