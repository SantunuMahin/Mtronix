from django.urls import path

from products import views

app_name = 'products'

urlpatterns = [
    path('', views.product_list, name='list'),
    path('new/', views.product_create, name='create'),
    path('<int:pk>/edit/', views.product_update, name='update'),
    path('groups/', views.group_list, name='group_list'),
    path('groups/new/', views.group_create, name='group_create'),
    path('groups/<int:pk>/edit/', views.group_update, name='group_update'),
    path('groups/<int:pk>/delete/', views.group_delete, name='group_delete'),
]
