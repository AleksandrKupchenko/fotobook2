from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import OrderForm, OrderFileForm
from .models import Order

@login_required
def order_list(request):
    orders = Order.objects.filter(owner=request.user)
    return render(request, 'orders/order_list.html', {'orders': orders})

@login_required
def order_create(request):
    if request.method == 'POST':
        order_form = OrderForm(request.POST)
        file_form = OrderFileForm(request.POST, request.FILES)

        if order_form.is_valid() and file_form.is_valid():
            order = order_form.save(commit=False)
            order.owner = request.user
            # простая формула цены: 1000 + 200*разворотов
            order.price = 1000 + order.spreads * 200
            order.save()

            file = file_form.save(commit=False)
            file.order = order
            file.save()

            return redirect('order_list')
    else:
        order_form = OrderForm()
        file_form = OrderFileForm()

    return render(request, 'orders/order_create.html', {
        'order_form': order_form,
        'file_form': file_form,
    })
