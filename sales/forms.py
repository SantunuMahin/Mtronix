from django import forms

from sales.models import Sale, SaleItem


class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ['customer_name']


class SaleItemForm(forms.ModelForm):
    class Meta:
        model = SaleItem
        fields = ['product', 'quantity', 'unit_price']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].empty_label = '— Select Product —'
        self.fields['product'].required = True
        self.fields['quantity'].widget.attrs.update({'min': '1', 'placeholder': 'Qty'})
        self.fields['unit_price'].widget.attrs.update({'placeholder': '0.00', 'step': '0.01'})
