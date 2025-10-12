from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('create/', views.create_order, name='order_create'),
    path('qr/<int:order_id>/', views.order_qr, name='order_qr'),
    path('update/<int:order_id>/<str:new_status>/', views.update_order_status, name='update_order_status'),
    path('update_status/', views.update_order_status_ajax, name='update_order_status_ajax'),
    path('detail/<int:order_id>/', views.order_detail, name='order_detail'),

]
