from rest_framework import serializers

from products.models import Product


class ProductSerializer(serializers.ModelSerializer):
    current_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'sku',
            'purchase_price',
            'selling_price',
            'low_stock_threshold',
            'current_stock',
            'created_at',
            'updated_at',
        ]

    def get_current_stock(self, product):
        return product.total_stock
