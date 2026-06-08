from rest_framework import serializers

from inventory.models import Inventory
from products.serializers import ProductSerializer


class InventorySerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(source='product.id', read_only=True)

    class Meta:
        model = Inventory
        fields = ['id', 'product_id', 'product', 'quantity', 'updated_at']
