from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
import pytz

from products.models import Product

BD_TZ = pytz.timezone('Asia/Dhaka')


def bd_now():
    """Return current datetime in Bangladesh timezone."""
    return timezone.now().astimezone(BD_TZ)


class PaymentStatus(models.TextChoices):
    PAID = 'PAID', 'Paid'
    PARTIAL = 'PARTIAL', 'Partial / Due'
    UNPAID = 'UNPAID', 'Unpaid'


class Sale(models.Model):
    customer_name = models.CharField(max_length=200, blank=True)
    customer_phone = models.CharField(max_length=50, blank=True)
    customer_address = models.TextField(blank=True)
    payment_status = models.CharField(
        max_length=10,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PAID,
        blank=True,
    )
    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
        blank=True,
    )
    sold_at = models.DateTimeField(default=bd_now)

    class Meta:
        ordering = ['-sold_at']

    @property
    def total_amount(self):
        return sum((item.total_amount for item in self.items.all()), Decimal('0.00'))

    @property
    def effective_paid_amount(self):
        """Amount actually paid by customer."""
        tot = self.total_amount
        if self.payment_status == PaymentStatus.PAID:
            return tot
        elif self.payment_status == PaymentStatus.UNPAID:
            return Decimal('0.00')
        else:  # PARTIAL
            if self.paid_amount is None or self.paid_amount <= Decimal('0.00'):
                return Decimal('0.00')
            return min(self.paid_amount, tot)

    @property
    def due_amount(self):
        """Outstanding balance due on this sale."""
        tot = self.total_amount
        paid = self.effective_paid_amount
        return max(Decimal('0.00'), tot - paid)

    @property
    def is_paid(self):
        return self.payment_status == PaymentStatus.PAID

    @property
    def is_partial(self):
        return self.payment_status == PaymentStatus.PARTIAL

    @property
    def is_unpaid(self):
        return self.payment_status == PaymentStatus.UNPAID

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
        status_label = f" [{self.get_payment_status_display()}]"
        return f'Sale #{self.pk} - {self.customer_name or "Walk-in"}{status_label}'


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sale_items',
    )
    custom_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Custom, unknown, or unlisted product name",
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    @property
    def total_amount(self):
        return self.quantity * self.unit_price

    @property
    def display_name(self):
        if self.product:
            return self.product.name
        return self.custom_name or 'Custom / Unknown Item'

    @property
    def sku(self):
        if self.product and self.product.sku:
            return self.product.sku
        return ''

    def save(self, *args, **kwargs):
        if self.product and not self.custom_name:
            self.custom_name = self.product.name
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.display_name} x {self.quantity} in Sale #{self.sale.pk}'