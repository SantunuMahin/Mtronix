from decimal import Decimal
from django import forms

from sales.models import Sale, SaleItem


class SaleForm(forms.ModelForm):
    paid_amount = forms.DecimalField(
        required=False,
        min_value=Decimal('0.00'),
        decimal_places=2,
        max_digits=12,
        widget=forms.NumberInput(attrs={
            'placeholder': 'Paid amount (BDT)',
            'step': '0.01',
            'min': '0.00',
            'class': 'paid-amount-input',
            'id': 'id_paid_amount',
        }),
    )

    class Meta:
        model = Sale
        fields = ['customer_name', 'customer_phone', 'customer_address', 'payment_status', 'paid_amount']
        widgets = {
            'customer_name': forms.TextInput(attrs={
                'placeholder': 'Customer name (e.g. John Doe)',
                'autocomplete': 'off',
            }),
            'customer_phone': forms.TextInput(attrs={
                'placeholder': 'Phone number (e.g. 01700-000000)',
                'autocomplete': 'off',
            }),
            'customer_address': forms.TextInput(attrs={
                'placeholder': 'Address / Area (e.g. Motijheel, Dhaka)',
                'autocomplete': 'off',
            }),
            'payment_status': forms.Select(attrs={
                'class': 'payment-status-select',
                'id': 'id_payment_status',
            }),
        }

    def clean_payment_status(self):
        status = self.cleaned_data.get('payment_status')
        return status if status else 'PAID'

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('payment_status')
        paid_amount = cleaned_data.get('paid_amount')

        if status == 'UNPAID':
            cleaned_data['paid_amount'] = Decimal('0.00')
        elif status == 'PARTIAL':
            if paid_amount is None:
                cleaned_data['paid_amount'] = Decimal('0.00')
        return cleaned_data


class SaleItemForm(forms.ModelForm):
    custom_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Custom / unlisted product name',
            'class': 'custom-name-input',
        }),
    )

    class Meta:
        model = SaleItem
        fields = ['product', 'custom_name', 'quantity', 'unit_price']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].empty_label = '— Select Product —'
        self.fields['product'].required = False
        self.fields['quantity'].widget.attrs.update({'min': '1', 'placeholder': 'Qty'})
        self.fields['unit_price'].widget.attrs.update({'placeholder': '0.00', 'step': '0.01'})

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        custom_name = (cleaned_data.get('custom_name') or '').strip()

        if not product and not custom_name:
            raise forms.ValidationError('Please select a product or enter a custom / unknown item name.')
        return cleaned_data
