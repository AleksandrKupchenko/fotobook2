from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.conf import settings
from .forms import OrderForm
from .models import Order, OrderFile
from PIL import Image
import os
import json
import qrcode
from django.http import JsonResponse

# ================================
# 📝 Проверки ролей
# ================================
def is_photographer(user):
    return user.groups.filter(name='photographers').exists()

def is_printer(user):
    return user.groups.filter(name='printers').exists()


# ================================
# 🛒 Создание заказа
# ================================
@login_required
def create_order(request):
    if request.method == 'POST':
        form = OrderForm(request.POST, request.FILES)
        files = request.FILES.getlist('files')

        if form.is_valid():
            valid_files = []
            errors = []

            for f in files:
                try:
                    img = Image.open(f)
                    w, h = img.size
                    if w < 2000 or h < 2000:
                        errors.append(f"Файл {f.name} слишком мал ({w}x{h}). Нужно минимум 2000x2000.")
                        continue
                    valid_files.append(f)
                except Exception:
                    errors.append(f"Файл {f.name} не является корректным изображением.")

            if errors:
                for err in errors:
                    messages.error(request, err)
                return render(request, 'orders/create_order.html', {'form': form})

            order = form.save(commit=False)
            order.user = request.user
            if hasattr(order, 'calculate_prices'):
                order.calculate_prices()
            order.save()

            # Сохраняем файлы (пример, если у вас есть связанная модель OrderFile)
            for f in valid_files:
                order.files.create(file=f)  # предполагается, что есть related_name='files'

            # Оплата
            if order.payment_method == 'qr':
                qr_text = f"ORDER:{order.id};AMOUNT:{order.total_price}"
                qr_img = qrcode.make(qr_text)
                pay_dir = os.path.join(settings.MEDIA_ROOT, 'payments')
                os.makedirs(pay_dir, exist_ok=True)
                qr_path = os.path.join(pay_dir, f'order_{order.id}_qr.png')
                qr_img.save(qr_path)
                order.payment_reference = f'payments/order_{order.id}_qr.png'
                order.payment_status = 'pending'
                order.save()
                return redirect('order_qr', order_id=order.id)
            elif order.payment_method == 'online':
                order.payment_status = 'pending'
                order.payment_reference = f'invoice:{order.id}'
                order.save()
                messages.info(request, "Платёж через gateway (заглушка).")
                return redirect('dashboard')
            else:
                order.payment_status = 'pending'
                order.save()
                messages.success(request, "Заказ создан. Оплата при получении.")
                return redirect('dashboard')
    else:
        form = OrderForm()

    return render(request, 'orders/create_order.html', {'form': form})



# ================================
# 🖼 QR-оплата
# ================================
@login_required
def order_qr(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    qr_url = settings.MEDIA_URL + order.payment_reference if order.payment_reference else None
    return render(request, 'orders/order_qr.html', {'order': order, 'qr_url': qr_url})


# ================================
# 📊 Универсальный dashboard
# ================================
@login_required
def dashboard(request):
    user = request.user
    is_photographer_flag = is_photographer(user)
    is_printer_flag = is_printer(user)

    if is_photographer_flag:
        orders = Order.objects.filter(user=user).order_by('-created_at')
    elif is_printer_flag:
        orders = Order.objects.all().order_by('status', '-created_at')
    else:
        orders = Order.objects.filter(user=user).order_by('-created_at')

    context = {
        'orders': orders,
        'is_photographer': is_photographer_flag,
        'is_printer': is_printer_flag,
    }
    return render(request, 'orders/dashboard.html', context)


# ================================
# 🔄 Обновление статуса заказа (для печатника)
# ================================
@login_required
@user_passes_test(is_printer)
def update_order_status(request, order_id, new_status):
    order = get_object_or_404(Order, id=order_id)
    if new_status in dict(Order.STATUS_CHOICES):
        order.status = new_status
        order.save(update_fields=['status'])
        messages.success(request, f"Статус заказа #{order.id} обновлён на «{order.get_status_display()}».")
    return redirect('dashboard')


# ================================
# ⚡ AJAX-обновление статуса
# ================================
@login_required
def update_order_status_ajax(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Требуется POST'}, status=405)

    user = request.user
    if not (user.is_staff or is_printer(user)):
        return JsonResponse({'success': False, 'error': 'Нет доступа'}, status=403)

    try:
        data = json.loads(request.body.decode('utf-8'))
        order_id = data.get('order_id')
        new_status = data.get('new_status')
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Ошибка JSON: {e}'}, status=400)

    if not order_id or not new_status:
        return JsonResponse({'success': False, 'error': 'Отсутствует order_id или new_status'}, status=400)

    order = get_object_or_404(Order, id=order_id)
    if new_status not in dict(Order.STATUS_CHOICES):
        return JsonResponse({'success': False, 'error': 'Неверный статус'}, status=400)

    order.status = new_status
    order.save(update_fields=['status'])

    return JsonResponse({
        'success': True,
        'status': new_status,
        'status_display': order.get_status_display(),
    })


# ================================
# 🖼 Просмотр заказа для печатника
# ================================
@login_required
@user_passes_test(is_printer)
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    files = OrderFile.objects.filter(order=order)
    return render(request, 'orders/order_detail.html', {'order': order, 'files': files})
