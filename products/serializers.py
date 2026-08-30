from rest_framework import serializers

from products.models import Product, ProductGroup


class ProductGroupSerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = ProductGroup
        fields = ['id', 'name', 'description', 'product_count', 'created_at', 'updated_at']

    def get_product_count(self, group):
        return group.products.count()


class ProductSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=50)
    group_name = serializers.CharField(source='group.name', read_only=True, default=None)
    current_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'group',
            'group_name',
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
