from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
import pytz

from products.models import Product

BD_TZ = pytz.timezone('Asia/Dhaka')


def bd_now():
    """Return current datetime in Bangladesh timezone."""
    return timezone.now().astimezone(BD_TZ)


class Sale(models.Model):
    customer_name = models.CharField(max_length=200, blank=True)
    sold_at = models.DateTimeField(default=bd_now)

    class Meta:
        ordering = ['-sold_at']

    @property
    def total_amount(self):
        return sum(item.total_amount for item in self.items.all())

    def save(self, *args, **kwargs):
        """Ensure sold_at is always in BD timezone."""
        if self.sold_at and self.sold_at.tzinfo is None:
            # If naive datetime, assume it's BD time
            self.sold_at = BD_TZ.localize(self.sold_at)
        elif self.sold_at and self.sold_at.tzinfo != BD_TZ:
            # If different timezone, convert to BD time
            self.sold_at = self.sold_at.astimezone(BD_TZ)
        super().save(*args, **kwargs)

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
        return f'{self.product.name} x {self.quantity} in Sale #{self.sale.pk}'