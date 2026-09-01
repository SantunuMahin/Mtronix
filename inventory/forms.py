from django import forms


class StockAdjustmentForm(forms.Form):
    REASON_ADD_CHOICES = [
        ('Supplier Restock / Delivery', 'Supplier Restock / Delivery'),
        ('Customer Return / Cancelled Sale', 'Customer Return / Cancelled Sale'),
        ('Inventory Audit Surplus', 'Inventory Audit Surplus / Found Stock'),
        ('Sample / Promotional Stock Received', 'Sample / Promotional Stock Received'),
        ('Other', 'Other (specify in notes)'),
    ]

    REASON_REMOVE_CHOICES = [
        ('Damaged / Broken / Defective', 'Damaged / Broken / Defective'),
        ('Expired / Deprecated Component', 'Expired / Deprecated Component'),
        ('Internal Store Use / Testing Demo', 'Internal Store Use / Testing Demo'),
        ('Inventory Audit Shortage / Missing', 'Inventory Audit Shortage / Missing'),
        ('Warranty Replacement Sent', 'Warranty Replacement Sent'),
        ('Other', 'Other (specify in notes)'),
    ]

    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'placeholder': 'Enter quantity (e.g. 10)',
            'class': 'quantity-input',
            'min': '1',
            'autofocus': 'autofocus',
        }),
    )
    reason = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Reason for adjustment (e.g. Supplier delivery, damaged unit)',
            'class': 'reason-input',
        }),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Additional memo, batch/serial number or reference (optional)...',
            'rows': 3,
            'class': 'notes-input',
        }),
    )

