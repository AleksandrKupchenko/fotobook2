from django.contrib import admin
from django.urls import path, include
from accounts.views import HomeView, DashboardView, RegisterView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', HomeView.as_view(), name='home'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('accounts/register/', RegisterView.as_view(), name='register'),
    path('accounts/', include('django.contrib.auth.urls')),  # login/logout/password_reset
    path('orders/', include('orders.urls')),

]
