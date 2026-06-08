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
        return f'{self.product.sku}: {self.quantity}'
