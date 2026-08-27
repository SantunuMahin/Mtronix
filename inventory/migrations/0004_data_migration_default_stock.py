from django.db import migrations

def create_default_stock_location(apps, schema_editor):
    StockLocation = apps.get_model('inventory', 'StockLocation')
    Inventory = apps.get_model('inventory', 'Inventory')
    Purchase = apps.get_model('purchases', 'Purchase')
    SaleItem = apps.get_model('sales', 'SaleItem')

    # Create default stock location
    default_location, _ = StockLocation.objects.get_or_create(name='Main Stock')

    # Update existing records
    Inventory.objects.filter(location__isnull=True).update(location=default_location)
    Purchase.objects.filter(location__isnull=True).update(location=default_location)
    SaleItem.objects.filter(location__isnull=True).update(location=default_location)

def reverse_migration(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_stocklocation_alter_inventory_options_and_more'),
        ('purchases', '0003_purchase_location'),
        ('sales', '0004_saleitem_location'),
    ]

    operations = [
        migrations.RunPython(create_default_stock_location, reverse_code=reverse_migration),
    ]
