from django.urls import path

from inventory import views

app_name = 'inventory'

urlpatterns = [
    path('', views.inventory_list, name='list'),
    path('<int:pk>/add/', views.inventory_add_stock, name='add_stock'),
    path('<int:pk>/remove/', views.inventory_remove_stock, name='remove_stock'),
]
