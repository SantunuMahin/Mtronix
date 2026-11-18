from django.urls import path
from accounts import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('users/', views.user_list, name='users'),
    path('users/<int:pk>/role/', views.user_update_role, name='user_role'),
    path('users/<int:pk>/toggle-active/', views.user_toggle_active, name='user_toggle_active'),
]
