from rest_framework import serializers

from inventory.services import InventoryService
from sales.models import Sale, SaleItem


class SaleItemSerializer(serializers.ModelSerializer):
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = SaleItem
        fields = ['product', 'custom_name', 'display_name', 'quantity', 'unit_price', 'total_amount']


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    due_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    effective_paid_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id',
            'customer_name',
            'customer_phone',
            'customer_address',
            'payment_status',
            'paid_amount',
            'effective_paid_amount',
            'due_amount',
            'total_amount',
            'sold_at',
            'items',
        ]
        read_only_fields = ['sold_at', 'effective_paid_amount', 'due_amount', 'total_amount']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        try:
            return InventoryService.create_sale(items=items_data, **validated_data)
        except ValueError as exc:
            raise serializers.ValidationError({'items': str(exc)}) from exc
