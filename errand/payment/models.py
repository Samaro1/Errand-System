from django.db import models


class Payment(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
        ("invalid", "Invalid Payment"),
    ]

    payer = models.ForeignKey("user.Customer", on_delete=models.CASCADE, related_name="payments_made")
    errand = models.ForeignKey("errands.Errand", on_delete=models.CASCADE, related_name="errand_payments")

    reference = models.CharField(max_length=100, unique=True)
    provider = models.CharField(max_length=50, default="Monnify")

    amount_expected = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default="NGN")
    payment_channel = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    sender_bank = models.CharField(max_length=100, blank=True, null=True)
    sender_account_number = models.CharField(max_length=20, blank=True, null=True)
    recipient_vda = models.CharField(max_length=20, blank=True, null=True)
    # Provider transfer/refund tracking
    provider_transfer_id = models.CharField(max_length=100, blank=True, null=True)
    provider_transfer_status = models.CharField(max_length=50, blank=True, null=True)
    provider_refund_id = models.CharField(max_length=100, blank=True, null=True)
    provider_refund_status = models.CharField(max_length=50, blank=True, null=True)

    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    refunded = models.BooleanField(default=False)
    refund_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.payer.username} - {self.reference} - {self.status}"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
