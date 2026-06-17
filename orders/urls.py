from django.urls import path
from . import views

urlpatterns = [
    # Главная страница панели заказов
    path('', views.dashboard, name='dashboard'),

    # === Этапы создания заказа ===
    path('select/', views.select_product, name='select_product'),                   # этап 1: выбор типа
    path('options/<str:product>/', views.product_options, name='product_options'),   # этап 2: параметры продукта
    path('upload/<int:order_id>/', views.upload_files, name='upload_files'),         # этап 3: загрузка файлов
    path('finish/<int:order_id>/', views.finish_order, name='finish_order'),         # этап 4: завершение заказа
    # этап 5: скачивание всех файлов для печати
    path('download/<int:order_id>/', views.download_order_files, name='download_order_files'),


    # === Дополнительные страницы ===
    path('qr/<int:order_id>/', views.order_qr, name='order_qr'),                    # QR-код заказа
    path('detail/<int:order_id>/', views.order_detail, name='order_detail'),        # страница деталей

    # === Обновление статусов ===
    path('update/<int:order_id>/<str:new_status>/', views.update_order_status, name='update_order_status'),
    path('update_status/', views.update_order_status_ajax, name='update_order_status_ajax'),

    # === Удаление заказов (для печатника) ===
    path('delete/<int:order_id>/', views.delete_order, name='delete_order'),
]
