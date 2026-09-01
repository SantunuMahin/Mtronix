from django.urls import path

from sales import views

app_name = 'sales'

urlpatterns = [
    path('', views.sale_list, name='list'),
    path('new/', views.sale_create, name='create'),
    path('<int:pk>/receipt/', views.sale_receipt_print, name='receipt_print'),
    path('<int:pk>/receipt.pdf', views.sale_receipt_pdf, name='receipt_pdf'),
    path('<int:pk>/toggle-status/', views.sale_toggle_payment_status, name='toggle_status'),
    path('statement/', views.customer_statement_view, name='customer_statement'),
    path('statement/', views.customer_statement_view, name='statement'),
    path('statement/pdf/', views.customer_statement_pdf, name='customer_statement_pdf'),
    path('statement/pdf/', views.customer_statement_pdf, name='statement_pdf'),
    path('report/pdf/', views.sales_report_pdf, name='report_pdf'),
    path('customer-lookup/', views.customer_lookup_api, name='customer_lookup'),
]

