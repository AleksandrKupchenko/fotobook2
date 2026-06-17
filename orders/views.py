# views.py
import json
import os
import io
import zipfile
from decimal import Decimal
from PIL import Image

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponseBadRequest, FileResponse
from django.contrib import messages
from django.conf import settings
from django.views.decorators.http import require_POST

from .models import Order, OrderFile
from .forms import OrderForm

# ✅ добавлено для WebSocket уведомлений
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


# ----------------------------
# Ролевые проверки
# ----------------------------
def is_photographer(user):
    return user.groups.filter(name='photographers').exists()


def is_printer(user):
    return user.groups.filter(name='printers').exists()


# ----------------------------
# Этап 1 — выбор продукта
# ----------------------------
@login_required
def select_product(request):
    products = [
        {'key': 'hard', 'title': 'Фотокнига — твёрдый переплёт', 'desc': 'Твёрдая обложка, развороты'},
        {'key': 'soft', 'title': 'Фотокнига — мягкие страницы', 'desc': 'Мягкая обложка, много страниц'},
        {'key': 'print', 'title': 'Печать на фотобумаге', 'desc': 'Отдельные отпечатки разных размеров'},
    ]
    return render(request, 'orders/select_product.html', {'products': products})


# ----------------------------
# Этап 2 — опции продукта
# ----------------------------
@login_required
def product_options(request, product):
    product = str(product)
    allowed = {'hard', 'soft', 'print'}
    if product not in allowed:
        messages.error(request, "Неверный тип продукта.")
        return redirect('select_product')

    if request.method == 'POST':
        qty_books = int(request.POST.get('quantity_books') or 1)
        spreads = int(request.POST.get('spreads') or 0)
        individual_spreads = int(request.POST.get('individual_spreads') or 0)
        pages = int(request.POST.get('pages') or 0)
        paper_size = request.POST.get('paper_size', '')
        print_type = request.POST.get('print_type', '')
        comment = request.POST.get('comment', '')

        order = Order.objects.create(
            user=request.user,
            product_type=product,
            quantity_books=qty_books,
            spreads=spreads or pages,
            individual_spreads=individual_spreads,
            print_type=print_type,
            paper_size=paper_size,
            comment=comment,
        )

        if hasattr(order, 'calculate_prices'):
            try:
                order.calculate_prices()
            except Exception:
                pass
            order.save()

        return redirect('upload_files', order_id=order.id)

    return render(request, 'orders/product_options.html', {'product': product})


# ----------------------------
# Этап 3 — загрузка файлов
# ----------------------------
@login_required
def upload_files(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    # ---- AJAX загрузка ----
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        result = {'saved': [], 'errors': []}
        for key in request.FILES:
            files = request.FILES.getlist(key)
            parts = key.split('-')
            book_index = 1
            slot_type = 'photo'
            slot_index = 0
            if len(parts) >= 5 and parts[0] == 'file' and parts[1] == 'book':
                try:
                    book_index = int(parts[2])
                except Exception:
                    book_index = 1
                slot_type = parts[3]

            for uploaded in files:
                # ✅ авто-нумерация для фото
                if slot_type == 'photo':
                    last = order.files.filter(slot_type='photo').order_by('-slot_index').first()
                    slot_index = (last.slot_index + 1) if last else 1
                else:
                    try:
                        slot_index = int(parts[4])
                    except Exception:
                        slot_index = 0

                try:
                    img = Image.open(uploaded)
                    w, h = img.size
                except Exception:
                    result['errors'].append({'field': key, 'filename': uploaded.name, 'error': 'Не изображение'})
                    continue

                MIN_W, MIN_H = 800, 600
                if slot_type == 'cover':
                    MIN_W, MIN_H = 1200, 800
                elif slot_type in ('spread', 'page'):
                    MIN_W, MIN_H = 1000, 700
                if w < MIN_W or h < MIN_H:
                    result['errors'].append({
                        'field': key,
                        'filename': uploaded.name,
                        'error': f'Слишком мал: {w}x{h}px (требуется >= {MIN_W}x{MIN_H})'
                    })
                    continue

                try:
                    of = OrderFile.objects.create(
                        order=order,
                        file=uploaded,
                        book_index=book_index,
                        slot_type=slot_type,
                        slot_index=slot_index,
                    )
                    result['saved'].append({
                        'id': of.id,
                        'url': of.file.url,
                        'filename': os.path.basename(of.file.name),
                        'width': w,
                        'height': h,
                    })
                except Exception as e:
                    result['errors'].append({'field': key, 'filename': uploaded.name, 'error': str(e)})

        return JsonResponse(result)

    # ---- Обычная форма загрузки ----
    if request.method == 'POST' and request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        saved = 0
        for key in request.FILES:
            for uploaded_file in request.FILES.getlist(key):
                parts = key.split('-')
                book_index = 1
                slot_type = 'photo'
                slot_index = 0
                if len(parts) >= 5 and parts[0] == 'file' and parts[1] == 'book':
                    try:
                        book_index = int(parts[2])
                    except Exception:
                        book_index = 1
                    slot_type = parts[3]

                # ✅ авто-нумерация для фото
                if slot_type == 'photo':
                    last = order.files.filter(slot_type='photo').order_by('-slot_index').first()
                    slot_index = (last.slot_index + 1) if last else 1
                else:
                    try:
                        slot_index = int(parts[4])
                    except Exception:
                        slot_index = 0

                try:
                    img = Image.open(uploaded_file)
                    w, h = img.size
                except Exception:
                    messages.error(request, f"Файл {uploaded_file.name} не является изображением.")
                    continue

                MIN_W, MIN_H = 800, 600
                if slot_type == 'cover':
                    MIN_W, MIN_H = 1200, 800
                elif slot_type in ('spread', 'page'):
                    MIN_W, MIN_H = 1000, 700

                if w < MIN_W or h < MIN_H:
                    messages.error(request, f"Файл {uploaded_file.name} ({slot_type}{slot_index}) слишком мал: {w}x{h}px (требуется >= {MIN_W}x{MIN_H}).")
                    continue

                try:
                    of = OrderFile.objects.create(
                        order=order,
                        file=uploaded_file,
                        book_index=book_index,
                        slot_type=slot_type,
                        slot_index=slot_index,
                    )
                    saved += 1
                except Exception:
                    try:
                        of = OrderFile(order=order, file=uploaded_file)
                        of.save()
                        saved += 1
                    except Exception:
                        messages.error(request, f"Не удалось сохранить файл {uploaded_file.name}")

        if saved:
            messages.success(request, f"Загружено {saved} файлов.")
        else:
            messages.info(request, "Нет загруженных файлов или все файлы были отклонены.")

        return redirect('finish_order', order_id=order.id)

    # ---- Формирование контекста ----
    books = []
    product_type = getattr(order, 'product_type', None) or 'print'
    qty = int(getattr(order, 'quantity_books', 1) or 1)
    spreads = int(getattr(order, 'spreads', 2) or 2)

    if product_type in ('hard', 'soft'):
        for i in range(1, qty + 1):
            slots = [{'slot_type': 'cover', 'slot_index': 0}]
            for si in range(1, spreads + 1):
                slots.append({'slot_type': 'spread' if product_type == 'hard' else 'page', 'slot_index': si})
            existing = order.files.filter(book_index=i).order_by('slot_type', 'slot_index')
            books.append({'index': i, 'slots': slots, 'existing': existing})
    else:
        existing = order.files.all()
        books = [{'index': 1, 'slots': [], 'existing': existing}]

    context = {'order': order, 'books': books, 'default_spreads': spreads, 'product_type': product_type}
    return render(request, 'orders/upload_files.html', context)


# ----------------------------
# Этап 4 — завершение заказа
# ----------------------------
@login_required
def finish_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if request.method == "POST":
        payment_method = request.POST.get("payment_method")
        delivery_type = request.POST.get("delivery_type")
        delivery_address = request.POST.get("delivery_address", "").strip()

        order.payment_method = payment_method
        order.delivery_type = delivery_type
        order.delivery_address = delivery_address

        if delivery_type == "courier":
            order.total_price += 1500
        elif delivery_type == "post":
            order.total_price += 2000

        if order.status == "new":
            order.status = "new"

        order.save(update_fields=["payment_method", "delivery_type", "delivery_address", "total_price", "status"])
        messages.success(request, "Заказ успешно завершён и отправлен в печать.")

        # ----------------------------
        # ✅ Отправка уведомления печатникам здесь
        # ----------------------------
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                print(f"[WS SEND] Подготавливаем отправку уведомления: order_id={order.id}, client={order.user.username}")
                async_to_sync(channel_layer.group_send)(
                    "printers",
                    {
                        "type": "send_new_order",
                        "order_id": order.id,
                        "client": order.user.username,
                        "product_type": order.get_product_type_display(),
                        "book_type": order.get_book_type_display(),
                        "spreads": order.spreads,
                        "comment": order.comment,
                    }
                )
                print(f"[WS SEND] Сообщение отправлено в группу 'printers'")
            else:
                print("[WS ERROR] channel_layer отсутствует")
        except Exception as e:
            print(f"[WS ERROR] Не удалось отправить уведомление: {e}")

        return redirect("dashboard")

    return render(request, "orders/finish_order.html", {"order": order})


# ----------------------------
# QR оплата
# ----------------------------
@login_required
def order_qr(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    qr_url = settings.MEDIA_URL + order.payment_reference if getattr(order, 'payment_reference', None) else None
    return render(request, 'orders/order_qr.html', {'order': order, 'qr_url': qr_url})


# ----------------------------
# Просмотр деталей заказа
# ----------------------------
@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    grouped = {}
    for f in order.files.all().order_by('book_index', 'slot_type', 'slot_index'):
        grouped.setdefault(getattr(f, 'book_index', 1), []).append(f)
    return render(request, 'orders/order_detail.html', {'order': order, 'grouped': grouped})


# ----------------------------
# Универсальный dashboard
# ----------------------------
@login_required
def dashboard(request):
    user = request.user
    photographer_flag = is_photographer(user)
    printer_flag = is_printer(user)

    status_filter = request.GET.get('status')
    orders = Order.objects.all()

    if photographer_flag:
        orders = orders.filter(user=user)
    elif not printer_flag:
        orders = orders.filter(user=user)

    if status_filter and status_filter != 'all':
        orders = orders.filter(status=status_filter)

    orders = orders.order_by('-created_at')
    context = {
        'orders': orders,
        'is_photographer': photographer_flag,
        'is_printer': printer_flag,
        'current_status': status_filter or 'all',
    }
    return render(request, 'orders/dashboard.html', context)


# ----------------------------
# Удаление заказа
# ----------------------------
@login_required
@user_passes_test(is_printer)
@require_POST
def delete_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order.delete()
    messages.success(request, f"Заказ #{order_id} успешно удалён.")
    return JsonResponse({'success': True})


# ----------------------------
# Обновление статуса
# ----------------------------
@login_required
@user_passes_test(is_printer)
def update_order_status(request, order_id, new_status):
    order = get_object_or_404(Order, id=order_id)
    valid = {c[0] for c in getattr(Order, 'STATUS_CHOICES', [])}

    if new_status in valid:
        order.status = new_status
        order.save(update_fields=['status'])

        if new_status == 'archived':
            for f in order.files.all():
                try:
                    if f.file and os.path.isfile(f.file.path):
                        os.remove(f.file.path)
                except Exception:
                    pass
            order.files.all().delete()

        messages.success(request, f"Статус заказа #{order.id} обновлён: {order.get_status_display()}")
    else:
        messages.error(request, "Неверный статус.")

    return redirect('dashboard')


# ----------------------------
# AJAX обновление статуса
# ----------------------------
@login_required
def update_order_status_ajax(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Требуется POST'}, status=405)

    user = request.user
    if not (user.is_staff or is_printer(user)):
        return JsonResponse({'success': False, 'error': 'Нет доступа'}, status=403)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'success': False, 'error': 'Неверный JSON'}, status=400)

    order_id = payload.get('order_id')
    new_status = payload.get('new_status')
    if not order_id or not new_status:
        return JsonResponse({'success': False, 'error': 'Отсутствует order_id или new_status'}, status=400)

    order = get_object_or_404(Order, id=order_id)
    valid = {c[0] for c in getattr(Order, 'STATUS_CHOICES', [])}
    if new_status not in valid:
        return JsonResponse({'success': False, 'error': 'Неверный статус'}, status=400)

    order.status = new_status
    order.save(update_fields=['status'])

    if new_status == 'archived':
        for f in order.files.all():
            try:
                if f.file and os.path.isfile(f.file.path):
                    os.remove(f.file.path)
            except Exception:
                pass
        order.files.all().delete()

    return JsonResponse({'success': True, 'status': new_status, 'status_display': order.get_status_display()})


# ----------------------------
# СКАЧИВАНИЕ ФОТО ДЛЯ ПЕЧАТИ
# ----------------------------
@login_required
@user_passes_test(is_printer)
def download_order_files(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    files = order.files.all().order_by('book_index', 'slot_type', 'slot_index')

    if not files.exists():
        return HttpResponseBadRequest("Нет файлов для скачивания.")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            if not f.file:
                continue
            try:
                fname = os.path.basename(f.file.name)
                ext = os.path.splitext(fname)[1].lower()
                if f.slot_type == "cover":
                    arcname = f"oblozhki/kniga_{f.book_index}_oblozhka{ext}"
                elif f.slot_type in ("spread", "page"):
                    arcname = f"razvoroty/kniga_{f.book_index}_razvorot_{f.slot_index}{ext}"
                elif f.slot_type == "photo":
                    arcname = f"photos/photo_{f.slot_index}{ext}"
                else:
                    arcname = f"other/kniga_{f.book_index}_{fname}"

                full_path = f.file.path
                if os.path.exists(full_path):
                    zf.write(full_path, arcname)
            except Exception as e:
                print(f"[ZIP ERROR] {e}")

    zip_buffer.seek(0)
    filename = f"order_{order_id}.zip"
    return FileResponse(zip_buffer, as_attachment=True, filename=filename)
