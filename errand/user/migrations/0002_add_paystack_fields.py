from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("user", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="bank_code",
            field=models.CharField(max_length=20, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="paystack_recipient_code",
            field=models.CharField(max_length=100, null=True, blank=True),
        ),
    ]
