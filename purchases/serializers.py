from rest_framework import serializers
from django.db import transaction

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
        try:
            with transaction.atomic():
                purchase = Purchase.objects.create(**validated_data)
                InventoryService.add_stock(purchase.product, purchase.quantity)
                return purchase
        except ValueError as exc:
            raise serializers.ValidationError({'quantity': str(exc)}) from exc
