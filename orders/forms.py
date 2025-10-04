from django import forms
from .models import Order, OrderFile
from PIL import Image

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['book_type', 'spreads']

class OrderFileForm(forms.ModelForm):
    class Meta:
        model = OrderFile
        fields = ['file']

    def clean_file(self):
        file = self.cleaned_data['file']
        try:
            img = Image.open(file)
            width, height = img.size
            if width < 2000 or height < 2000:
                raise forms.ValidationError("Изображение слишком маленькое! Нужно минимум 2000x2000 пикселей.")
        except Exception:
            raise forms.ValidationError("Файл не является корректным изображением.")
        return file
