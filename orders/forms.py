from django import forms
from .models import Order
from django.core.exceptions import ValidationError

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            'book_type', 'spreads', 'comment',
            'delivery_type', 'delivery_address',
            'payment_method'
        ]
        widgets = {
            'comment': forms.Textarea(attrs={'rows':3}),
            'delivery_address': forms.TextInput(attrs={'placeholder':'Улица, дом, кв. (если требуется)'}),
        }

    def clean(self):
        cleaned = super().clean()
        delivery = cleaned.get('delivery_type')
        addr = cleaned.get('delivery_address')
        payment = cleaned.get('payment_method')

        if delivery != 'pickup' and not addr:
            raise ValidationError("При выборе доставки укажите адрес.")

        # можно добавить дополнительные проверки для payment_method
        return cleaned
