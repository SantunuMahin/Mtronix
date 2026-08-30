from django import forms

from products.models import Product, ProductGroup


class ProductGroupForm(forms.ModelForm):
    class Meta:
        model = ProductGroup
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional group description...'}),
        }


class ProductForm(forms.ModelForm):
    sku = forms.CharField(max_length=50, required=False)

    class Meta:
        model = Product
        fields = ['name', 'group', 'sku', 'purchase_price', 'selling_price', 'low_stock_threshold']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['group'].queryset = ProductGroup.objects.all().order_by('name')
        self.fields['group'].empty_label = '— Select Group (Optional) —'
        self.fields['group'].required = False

    def clean_sku(self):
        sku = self.cleaned_data.get('sku')
        if sku:
            sku = sku.strip()
            return sku if sku else None
        return None
