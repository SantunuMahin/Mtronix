from django import forms


class StockAdjustmentForm(forms.Form):
    quantity = forms.IntegerField(min_value=1)
