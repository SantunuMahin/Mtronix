from django.urls import path

from purchases import views

app_name = 'purchases'

urlpatterns = [
    path('', views.purchase_list, name='list'),
    path('new/', views.purchase_create, name='create'),
]
