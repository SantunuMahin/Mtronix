from django.core.validators import MinValueValidator
from django.db import models

from products.models import Product


class Sale(models.Model):
    customer_name = models.CharField(max_length=200, blank=True)
    sold_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_amount(self):
        return sum(item.total_amount for item in self.items.all())

    def __str__(self):
        return f'Sale #{self.pk} - {self.customer_name or "Walk-in"}'


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='sale_items')
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    @property
    def total_amount(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f'{self.product.sku} x {self.quantity} in Sale #{self.sale.pk}'
