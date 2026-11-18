from django.urls import path

from products import views

app_name = 'products'

urlpatterns = [
    path('', views.product_list, name='list'),
    path('export/csv/', views.product_export_csv, name='export_csv'),
    path('new/', views.product_create, name='create'),
    path('<int:pk>/edit/', views.product_update, name='update'),
    path('<int:pk>/delete/', views.product_delete, name='delete'),
    path('<int:pk>/barcode/', views.product_barcode_label, name='barcode_label'),
    path('barcode/batch/', views.product_barcode_batch_print, name='barcode_batch_print'),
    path('api/generate-sku/', views.api_generate_sku, name='api_generate_sku'),
    path('api/barcode-preview/', views.api_preview_barcode, name='api_preview_barcode'),
    path('groups/', views.group_list, name='group_list'),
    path('groups/new/', views.group_create, name='group_create'),
    path('groups/<int:pk>/edit/', views.group_update, name='group_update'),
    path('groups/<int:pk>/delete/', views.group_delete, name='group_delete'),
]
