from django.urls import path

from sales import views

app_name = 'sales'

urlpatterns = [
    path('', views.sale_list, name='list'),
    path('new/', views.sale_create, name='create'),
    path('<int:pk>/receipt.pdf', views.sale_receipt_pdf, name='receipt_pdf'),
    path('report/pdf/', views.sales_report_pdf, name='report_pdf'),
]
