from rest_framework import serializers

from inventory.services import InventoryService
from purchases.models import Purchase


class PurchaseSerializer(serializers.ModelSerializer):
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Purchase
        fields = [
            'id',
            'supplier',
            'product',
            'quantity',
            'unit_price',
            'total_amount',
            'purchased_at',
        ]
        read_only_fields = ['purchased_at']

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None
        try:
            return InventoryService.create_purchase(user=user, **validated_data)
        except ValueError as exc:
            raise serializers.ValidationError({'quantity': str(exc)}) from exc
