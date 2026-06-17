from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User


class Order(models.Model):
    BOOK_TYPES = [
        ('classic', 'Классическая'),
        ('premium', 'Премиум'),
        ('mini', 'Мини'),
    ]

    PRODUCT_TYPES = [
        ('hard', 'Твёрдая обложка'),
        ('soft', 'Мягкая обложка'),
        ('print', 'Печать без обложки'),
    ]

    PRINT_TYPES = [
        ('digital', 'Цифровая печать'),
        ('offset', 'Офсетная печать'),
    ]

    PAPER_SIZES = [
        ('a4', 'A4'),
        ('a5', 'A5'),
        ('square', 'Квадрат'),
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

    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('in_progress', 'Принят'),
        ('printing', 'Печатается'),
        ('done', 'Готов'),
        ('archived', 'В архиве'),
    ]

    # --- Основное ---
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    created_at = models.DateTimeField(auto_now_add=True)

    # --- Новые поля ---
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES, default='hard')
    quantity_books = models.PositiveIntegerField(default=1)
    individual_spreads = models.BooleanField(default=False)
    print_type = models.CharField(max_length=20, choices=PRINT_TYPES, default='digital')
    paper_size = models.CharField(max_length=20, choices=PAPER_SIZES, default='a4')

    # --- Существующие поля ---
    book_type = models.CharField(max_length=20, choices=BOOK_TYPES)
    spreads = models.PositiveIntegerField(default=10)
    comment = models.TextField(blank=True)

    # --- Доставка и оплата ---
    delivery_type = models.CharField(max_length=20, choices=DELIVERY_CHOICES, default='pickup')
    delivery_address = models.CharField(max_length=512, blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    spreads_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    payment_reference = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')

    def __str__(self):
        return f"Заказ #{self.id} — {self.user.username} — {self.get_book_type_display()}"

    # --- Расчёт цен ---
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

    # --- Дополнительно для соответствия JS ---
    HARD_BOOK_MULTIPLIER = Decimal('900')
    SOFT_BOOK_BASE = Decimal('1900')
    SOFT_BOOK_SPREAD_PRICE = Decimal('400')
    PRINT_PRICES = {
        '10x15': Decimal('70'),
        '13x18': Decimal('150'),
        '15x20': Decimal('270'),
        '20x30': Decimal('500'),
    }

    def calculate_prices(self):
        """Вычислить base_price, spreads_price, delivery_cost и total_price."""
        total = Decimal('0.00')

        if self.product_type == 'hard':
            total = Decimal(self.quantity_books) * Decimal(self.spreads) * self.HARD_BOOK_MULTIPLIER
            self.base_price = Decimal(self.quantity_books) * self.HARD_BOOK_MULTIPLIER
            self.spreads_price = Decimal(self.spreads) * self.HARD_BOOK_MULTIPLIER
        elif self.product_type == 'soft':
            total = Decimal(self.quantity_books) * (self.SOFT_BOOK_BASE + Decimal(self.spreads) * self.SOFT_BOOK_SPREAD_PRICE)
            self.base_price = Decimal(self.quantity_books) * self.SOFT_BOOK_BASE
            self.spreads_price = Decimal(self.spreads) * self.SOFT_BOOK_SPREAD_PRICE
        else:  # print
            price_per_photo = self.PRINT_PRICES.get(self.paper_size, Decimal('0.00'))
            total = Decimal(self.spreads) * price_per_photo
            self.base_price = Decimal('0.00')
            self.spreads_price = Decimal(self.spreads) * price_per_photo

        self.delivery_cost = self.DELIVERY_PRICE.get(self.delivery_type, Decimal('0.00'))
        self.total_price = total + self.delivery_cost
        return self.total_price


class OrderFile(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='orders/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # --- Поля для совместимости с upload.js ---
    book_index = models.PositiveIntegerField(default=1)
    slot_type = models.CharField(max_length=20, default='spread')  # cover, spread, photo
    slot_index = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Файл для заказа #{self.order.id} — книга {self.book_index} — {self.slot_type} {self.slot_index}"
