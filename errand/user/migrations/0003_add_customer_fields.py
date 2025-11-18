from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('user', '0002_add_paystack_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='last_login',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='customer',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
    ]
