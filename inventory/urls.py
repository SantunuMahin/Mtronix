from django.urls import path

from inventory import views

app_name = 'inventory'

urlpatterns = [
    path('', views.inventory_list, name='list'),
    path('logs/', views.inventory_logs, name='logs'),
    path('report/pdf/', views.inventory_report_pdf, name='report_pdf'),
    path('<int:pk>/add/', views.inventory_add_stock, name='add_stock'),
    path('<int:pk>/remove/', views.inventory_remove_stock, name='remove_stock'),
]

