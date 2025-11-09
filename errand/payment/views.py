import logging
import requests
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from .serializers import PaymentSerializer, InitializePaymentSerializer
from errands.models import Errand

from .models import Payment

logger = logging.getLogger(__name__)

PAYSTACK_SECRET_KEY = getattr(settings, "PAYSTACK_SECRET_KEY", None)
PAYSTACK_BASE_URL = getattr(settings, "PAYSTACK_BASE_URL", "https://api.paystack.co")


# ------------------ Initialize Payment ------------------
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def initialize_payment(request):
    """
    Initialize a Paystack payment and return authorization URL.
    """
    user= request.user
    serializer = InitializePaymentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    errand_id = serializer.validated_data["errand_id"]
    amount = serializer.validated_data["amount"]

    if not amount or not errand_id:
        return Response({"error": "Amount and errand_id are required."}, status=status.HTTP_400_BAD_REQUEST)

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    # Use fallbacks if using the project's simple Customer model which may not have
    # full Django User methods/fields (email, get_full_name).
    email = getattr(user, "email", f"{getattr(user, 'username', 'user')}@example.com")
    try:
        name = user.get_full_name()
    except Exception:
        name = getattr(user, "username", "user")

    data = {
        "email": email,
        "amount": int(float(amount) * 100),  # Paystack expects amount in kobo
        "metadata": {"name": name, "errand_id": errand_id},
        "callback_url": "https://dummyforredirect.com/api/payments/verify/",
    }

    try:
        response = requests.post(f"{PAYSTACK_BASE_URL}/transaction/initialize", headers=headers, json=data)
        res_data = response.json()

        if not res_data.get("status"):
            raise Exception(res_data.get("message", "Paystack initialization failed."))

        # Save payment record
        with transaction.atomic():
            Payment.objects.create(
                payer=user,
                errand_id=errand_id,
                reference=res_data["data"]["reference"],
                provider="Paystack",
                amount_expected=amount,
                status="pending",
            )

        return Response({
            "authorization_url": res_data["data"]["authorization_url"],
            "access_code": res_data["data"]["access_code"],
            "reference": res_data["data"]["reference"],
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Paystack Init Error: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ------------------ Verify Payment ------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def verify_payment(request, reference):
    """
    Verify Paystack payment and update Payment record.
    """
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}

    try:
        response = requests.get(f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}", headers=headers)
        res_data = response.json()

        if not res_data.get("status"):
            return Response({"error": res_data.get("message", "Verification failed.")}, status=status.HTTP_400_BAD_REQUEST)

        data = res_data["data"]
        status_text = data["status"]

        payment = Payment.objects.filter(reference=reference).first()
        if not payment:
            return Response({"error": "Payment not found."}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            payment.status = "success" if status_text == "success" else "failed"
            payment.amount_paid = float(data.get("amount", 0)) / 100
            payment.paid_at = timezone.now()
            payment.payment_channel = data.get("channel")
            payment.sender_bank = data.get("authorization", {}).get("bank")
            payment.sender_account_number = data.get("authorization", {}).get("last4")
            payment.save()

        return Response({
            "message": "Payment verified successfully",
            "status": payment.status,
            "amount_paid": payment.amount_paid,
            "channel": payment.payment_channel,
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Paystack Verify Error: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ------------------ Paystack Webhook ------------------
@api_view(["POST"])
@permission_classes([AllowAny])
def paystack_webhook(request):
    """
    Handle Paystack Webhook events (payment.success, charge.success, etc.)
    """
    event = request.data
    reference = event.get("data", {}).get("reference")

    if not reference:
        return Response({"error": "Invalid webhook payload."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        payment = Payment.objects.filter(reference=reference).first()
        if not payment:
            logger.warning(f"Webhook: No payment found for reference {reference}")
            return Response({"message": "Payment not found."}, status=status.HTTP_404_NOT_FOUND)

        event_type = event.get("event")
        if event_type in ["charge.success", "payment.success"]:
            with transaction.atomic():
                payment.status = "success"
                payment.amount_paid = float(event["data"]["amount"]) / 100
                payment.paid_at = timezone.now()
                payment.sender_bank = event["data"]["authorization"]["bank"]
                payment.sender_account_number = event["data"]["authorization"]["last4"]
                payment.save()

            logger.info(f"Payment {reference} updated via webhook.")
            return Response({"message": "Payment updated successfully."}, status=status.HTTP_200_OK)

        logger.info(f"Unhandled webhook event: {event_type}")
        return Response({"message": "Event ignored."}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Webhook Error: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_payments(request):
    """
    List all payments made by the logged-in user.
    """
    payments = Payment.objects.filter(payer=request.user)
    serializer = PaymentSerializer(payments, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def payment_detail(request, reference):
    """
    Retrieve details of a specific payment by reference.
    """
    payment = get_object_or_404(Payment, reference=reference)
    serializer = PaymentSerializer(payment)
    return Response(serializer.data, status=status.HTTP_200_OK)