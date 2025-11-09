from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payment", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="provider_transfer_id",
            field=models.CharField(max_length=100, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="provider_transfer_status",
            field=models.CharField(max_length=50, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="provider_refund_id",
            field=models.CharField(max_length=100, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="provider_refund_status",
            field=models.CharField(max_length=50, null=True, blank=True),
        ),
    ]
