"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter

from inventory.views import InventoryViewSet, dashboard
from products.views import ProductGroupViewSet, ProductViewSet
from purchases.views import PurchaseViewSet
from sales.views import SaleViewSet
from suppliers.views import SupplierViewSet

api_router = DefaultRouter()
api_router.register(r'products', ProductViewSet, basename='api-products')
api_router.register(r'product-groups', ProductGroupViewSet, basename='api-product-groups')
api_router.register(r'inventory', InventoryViewSet, basename='api-inventory')
api_router.register(r'sales', SaleViewSet, basename='api-sales')
api_router.register(r'purchases', PurchaseViewSet, basename='api-purchases')
api_router.register(r'suppliers', SupplierViewSet, basename='api-suppliers')

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('sw.js', TemplateView.as_view(template_name='sw.js', content_type='application/javascript'), name='service_worker'),
    path('admin/', admin.site.urls),
    path('api/', include(api_router.urls)),
    path('accounts/', include('accounts.urls')),
    path('products/', include('products.urls')),
    path('suppliers/', include('suppliers.urls')),
    path('purchases/', include('purchases.urls')),
    path('sales/', include('sales.urls')),
    path('inventory/', include('inventory.urls')),
]
