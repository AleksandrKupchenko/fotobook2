from django.db import models
from django.contrib.auth.models import User

class Order(models.Model):
    BOOK_TYPES = [
        ('standart', 'Стандартная фотокнига'),
        ('premium', 'Премиум фотокнига'),
    ]

    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('in_progress', 'В работе'),
        ('done', 'Готово'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    book_type = models.CharField(max_length=50, choices=BOOK_TYPES, default='standart')
    spreads = models.PositiveIntegerField(default=10)  # количество разворотов
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Заказ #{self.id} ({self.owner.username})"
    

# отдельная модель для загружаемых файлов
class OrderFile(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='orders/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
