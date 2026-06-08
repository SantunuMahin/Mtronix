from django.urls import path

from products import views

app_name = 'products'

urlpatterns = [
    path('', views.product_list, name='list'),
    path('new/', views.product_create, name='create'),
    path('<int:pk>/edit/', views.product_update, name='update'),
]
