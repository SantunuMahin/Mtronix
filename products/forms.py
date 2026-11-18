from django import forms

from products.models import Product, ProductGroup


class ProductGroupForm(forms.ModelForm):
    class Meta:
        model = ProductGroup
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. LED Drivers, Power Supplies, Sensors...'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional category description, specifications, or notes...'}),
        }


from decimal import Decimal

class ProductForm(forms.ModelForm):
    sku = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. MTX-10029 (or click Generate)'}),
        help_text="Unique SKU or Barcode identifier."
    )
    purchase_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.00'),
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
        help_text="Unit cost price from supplier (BDT)"
    )

    class Meta:
        model = Product
        fields = ['name', 'group', 'sku', 'purchase_price', 'selling_price', 'low_stock_threshold']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. 12V 60W Power Supply'}),
            'selling_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'low_stock_threshold': forms.NumberInput(attrs={'min': '0', 'placeholder': '5'}),
        }
        help_texts = {
            'selling_price': 'Standard retail price for customers (BDT)',
            'low_stock_threshold': 'Trigger low stock alert when inventory reaches this level',
        }

    def clean_purchase_price(self):
        val = self.cleaned_data.get('purchase_price')
        return val if val is not None else Decimal('0.00')

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.purchase_price is None:
            instance.purchase_price = Decimal('0.00')
        if commit:
            instance.save()
        return instance

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['group'].queryset = ProductGroup.objects.all().order_by('name')
        self.fields['group'].empty_label = '— Select Group / Category (Optional) —'
        self.fields['group'].required = False

    def clean_sku(self):
        sku = self.cleaned_data.get('sku')
        if sku:
            sku = sku.strip()
            return sku if sku else None
        return None
