from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User


class Order(models.Model):
    BOOK_TYPES = [
        ('classic', 'Классическая'),
        ('premium', 'Премиум'),
        ('mini', 'Мини'),
    ]

    DELIVERY_CHOICES = [
        ('pickup', 'Самовывоз (0 ₸)'),
        ('courier', 'Курьер (доставка по городу)'),
        ('post', 'Почта / EMS / Посылка'),
    ]

    PAYMENT_METHODS = [
        ('cash', 'Наличные при получении'),
        ('qr', 'Оплата по QR'),
        ('online', 'Онлайн-платёж (gateway)'),
    ]

    PAYMENT_STATUS = [
        ('pending', 'Ожидает оплаты'),
        ('paid', 'Оплачено'),
        ('failed', 'Неудача'),
    ]

    # ✅ Новые статусы
    STATUS_CHOICES = [
        ('accepted', 'Принят'),
        ('printing', 'Заказ печатается'),
        ('ready', 'Готов к выдаче'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    book_type = models.CharField(max_length=20, choices=BOOK_TYPES)
    spreads = models.PositiveIntegerField(default=10)
    comment = models.TextField(blank=True)

    # доставка и адрес
    delivery_type = models.CharField(max_length=20, choices=DELIVERY_CHOICES, default='pickup')
    delivery_address = models.CharField(max_length=512, blank=True)

    # цена
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    spreads_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # оплата
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    payment_reference = models.CharField(max_length=255, blank=True)

    # производственный статус
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='accepted')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Заказ #{self.id} — {self.user.username} — {self.get_book_type_display()}"

    # --- Константы расчёта ---
    PRICE_BASE = {
        'classic': Decimal('1500.00'),
        'premium': Decimal('3000.00'),
        'mini': Decimal('800.00'),
    }
    PRICE_PER_SPREAD = Decimal('200.00')
    DELIVERY_PRICE = {
        'pickup': Decimal('0.00'),
        'courier': Decimal('600.00'),
        'post': Decimal('1200.00'),
    }

    def calculate_prices(self):
        """Вычислить base_price, spreads_price, delivery_cost и total_price."""
        base = self.PRICE_BASE.get(self.book_type, Decimal('0.00'))
        spreads_price = Decimal(self.spreads) * self.PRICE_PER_SPREAD
        delivery = self.DELIVERY_PRICE.get(self.delivery_type, Decimal('0.00'))

        self.base_price = base
        self.spreads_price = spreads_price
        self.delivery_cost = delivery
        self.total_price = base + spreads_price + delivery
        return self.total_price

    # --- Утилиты статуса ---
    def is_paid(self):
        """Возвращает True, если заказ оплачен."""
        return self.payment_status == 'paid'

    def mark_accepted(self):
        self.status = 'accepted'
        self.save(update_fields=['status'])

    def mark_printing(self):
        self.status = 'printing'
        self.save(update_fields=['status'])

    def mark_ready(self):
        self.status = 'ready'
        self.save(update_fields=['status'])


# 💾 Модель файлов заказа
class OrderFile(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='orders/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Файл для заказа #{self.order.id}"
