from django.db import migrations

def create_initial_currencies(apps, schema_editor):
    """
    Create the initial currency data:
    USD (base), EUR, and RUB with their exchange rates
    """
    Currency = apps.get_model('banking', 'Currency')
    
    # Create USD (base currency)
    Currency.objects.create(
        code='USD',
        name='US Dollar',
        symbol='$',
        exchange_rate=1.0,
        is_active=True
    )
    
    # Create EUR
    Currency.objects.create(
        code='EUR',
        name='Euro',
        symbol='€',
        exchange_rate=0.85,  # 1 USD = 0.85 EUR
        is_active=True
    )
    
    # Create RUB
    Currency.objects.create(
        code='RUB',
        name='Russian Ruble',
        symbol='₽',
        exchange_rate=75.0,  # 1 USD = 75 RUB
        is_active=True
    )

def delete_initial_currencies(apps, schema_editor):
    """
    Delete the initial currencies when rolling back the migration
    """
    Currency = apps.get_model('banking', 'Currency')
    Currency.objects.filter(code__in=['USD', 'EUR', 'RUB']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('banking', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            create_initial_currencies,
            delete_initial_currencies
        ),
    ]
