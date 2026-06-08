from django.db.models.signals import post_save
from django.dispatch import receiver

from inventory.models import Inventory
from products.models import Product


@receiver(post_save, sender=Product)
def create_product_inventory(sender, instance, created, **kwargs):
    if created:
        Inventory.objects.get_or_create(product=instance)
