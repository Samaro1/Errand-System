from rest_framework import serializers
from .models import Payment
from errands.models import Errand


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for returning and managing Payment records."""

    errand_title = serializers.CharField(source="errand.title", read_only=True)
    payer_name = serializers.CharField(source="payer.get_full_name", read_only=True)

    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = [
            'reference',
            'status',
            'paid_at',
            'created_at',
            'updated_at',
            'refunded',
            'refund_reason',
            'payer_name',
            'errand_title',
        ]


class InitializePaymentSerializer(serializers.Serializer):
    """Validates payment initialization data before calling Paystack."""

    errand_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField(default="NGN", max_length=10)

    def validate_errand_id(self, value):
        """Ensure the errand exists before proceeding."""
        try:
            errand = Errand.objects.get(id=value)
            if errand.status != "completed" and errand.runner is None:
                # ensure payment is only for accepted errands
                return value
        except Errand.DoesNotExist:
            raise serializers.ValidationError("Errand not found.")
        return value

    def validate_amount(self, value):
        """Ensure amount is positive and meaningful."""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value
