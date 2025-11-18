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
from .utils import release_payment, refund_payment
import uuid
from django.utils import timezone as dj_timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages
from django.urls import reverse

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
            # If payment succeeded, mark the linked errand as posted (visible)
            try:
                if payment.status == "success" and getattr(payment, "errand", None):
                    err = payment.errand
                    err.status = "pending"
                    err.save()
            except Exception:
                logger.exception("Failed to update errand status after payment verification")

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

            # mark errand visible
            try:
                if getattr(payment, "errand", None):
                    payment.errand.status = "pending"
                    payment.errand.save()
            except Exception:
                logger.exception("Failed to update errand status from webhook")

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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_simulate_deposit(request, payment_id):
    """API: Simulate a deposit (mark payment as paid) for sandbox/testing.

    Only enabled when PAYSTACK_FAKE_IN_TESTS or DEBUG or running tests.
    Only the payer (or staff) may simulate their own deposit.
    """
    import sys
    enabled = getattr(settings, "PAYSTACK_FAKE_IN_TESTS", False) or getattr(settings, "DEBUG", False) or ("test" in sys.argv)
    if not enabled:
        return Response({"error": "Sandbox disabled"}, status=status.HTTP_403_FORBIDDEN)

    payment = get_object_or_404(Payment, id=payment_id)
    # Only payer may mark their own payment as paid (or staff)
    if payment.payer != request.user and not request.user.is_staff:
        return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

    payment.amount_paid = payment.amount_expected
    payment.status = "success"
    payment.paid_at = dj_timezone.now()
    payment.save()
    # mark errand visible
    try:
        if getattr(payment, "errand", None):
            payment.errand.status = "pending"
            payment.errand.save()
    except Exception:
        logger.exception("Failed to update errand after api_simulate_deposit")

    serializer = PaymentSerializer(payment)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_simulate_payout(request, payment_id):
    """API: Simulate a payout (release payment to runner) for sandbox/testing.

    Only the errand creator or staff can trigger payout.
    """
    import sys
    enabled = getattr(settings, "PAYSTACK_FAKE_IN_TESTS", False) or getattr(settings, "DEBUG", False) or ("test" in sys.argv)
    if not enabled:
        return Response({"error": "Sandbox disabled"}, status=status.HTTP_403_FORBIDDEN)

    payment = get_object_or_404(Payment, id=payment_id)
    if not payment.errand:
        return Response({"error": "Payment has no associated errand"}, status=status.HTTP_400_BAD_REQUEST)

    if request.user != payment.errand.creator and not request.user.is_staff:
        return Response({"error": "Only errand creator can trigger payout"}, status=status.HTTP_403_FORBIDDEN)

    try:
        res = release_payment(payment)
    except Exception as e:
        logger.exception("api_simulate_payout error")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    serializer = PaymentSerializer(payment)
    return Response({"payment": serializer.data, "result": res}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_simulate_refund(request, payment_id):
    """API: Simulate a refund for sandbox/testing.

    Only the errand creator or staff may trigger a refund via API.
    """
    import sys
    enabled = getattr(settings, "PAYSTACK_FAKE_IN_TESTS", False) or getattr(settings, "DEBUG", False) or ("test" in sys.argv)
    if not enabled:
        return Response({"error": "Sandbox disabled"}, status=status.HTTP_403_FORBIDDEN)

    payment = get_object_or_404(Payment, id=payment_id)
    if request.user != payment.errand.creator and not request.user.is_staff:
        return Response({"error": "Only errand creator can trigger refund"}, status=status.HTTP_403_FORBIDDEN)

    try:
        res = refund_payment(payment, reason=request.data.get("reason"))
    except Exception as e:
        logger.exception("api_simulate_refund error")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    serializer = PaymentSerializer(payment)
    return Response({"payment": serializer.data, "result": res}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
def sandbox_operate(request):
    """
    Sandbox helper to simulate payment -> payout -> refund flows for frontend demos.
    Expected JSON: { action: 'pay'|'payout'|'refund', errand_id: int, amount: decimal (optional), reason: str (optional) }
    Only enabled when DEBUG=True or PAYSTACK_FAKE_IN_TESTS is truthy.
    """
    # Allow sandbox when explicitly enabled, when DEBUG=True, or when running tests
    import sys
    enabled = getattr(settings, "PAYSTACK_FAKE_IN_TESTS", False) or getattr(settings, "DEBUG", False) or ("test" in sys.argv)
    if not enabled:
        return Response({"error": "Sandbox endpoint disabled"}, status=status.HTTP_403_FORBIDDEN)

    action = request.data.get("action")
    errand_id = request.data.get("errand_id")
    amount = request.data.get("amount")
    reason = request.data.get("reason")

    if not action or not errand_id:
        return Response({"error": "action and errand_id are required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        errand = Errand.objects.get(id=errand_id)
    except Errand.DoesNotExist:
        return Response({"error": "Errand not found"}, status=status.HTTP_404_NOT_FOUND)

    # For pay: create or update a Payment as paid
    if action == "pay":
        payer = errand.creator
        # use provided amount or errand.price
        amt = amount or errand.price
        reference = f"SIM-{uuid.uuid4().hex[:12].upper()}"
        paid_at = dj_timezone.now()

        payment, created = Payment.objects.get_or_create(
            errand=errand,
            payer=payer,
            defaults={
                "reference": reference,
                "provider": "Paystack-Sandbox",
                "amount_expected": amt,
                "amount_paid": amt,
                "status": "success",
                "paid_at": paid_at,
            },
        )
        if not created:
            # update existing
            payment.reference = payment.reference or reference
            payment.amount_paid = amt
            payment.status = "success"
            payment.paid_at = paid_at
            payment.save()

        # Ensure errand becomes visible once the creator has paid
        try:
            errand.status = "pending"
            errand.save()
        except Exception:
            logger.exception("Failed to mark errand pending after sandbox pay")

        receipt = {
            "reference": payment.reference,
            "amount": float(payment.amount_paid),
            "paid_at": payment.paid_at.isoformat(),
            "provider": payment.provider,
            "status": payment.status,
        }
        return Response({"receipt": receipt}, status=status.HTTP_200_OK)

    # For payout: ensure payment exists and is paid, then call release_payment
    elif action == "payout":
        payment = Payment.objects.filter(errand=errand, status__in=["success", "pending"]).first()
        if not payment:
            return Response({"error": "No paid payment found for this errand"}, status=status.HTTP_404_NOT_FOUND)

        res = release_payment(payment)
        # Build transfer receipt
        transfer = {
            "provider_transfer_id": getattr(payment, "provider_transfer_id", None),
            "provider_transfer_status": getattr(payment, "provider_transfer_status", None),
            "recipient": getattr(payment, "recipient_vda", None) or getattr(payment.errand.runner, "userprofile", None) and getattr(payment.errand.runner.userprofile, "paystack_recipient_code", None),
            "payment_reference": payment.reference,
            "amount": float(payment.amount_paid or payment.amount_expected),
        }
        return Response({"transfer": transfer, "result": res}, status=status.HTTP_200_OK)

    # For refund: call refund_payment
    elif action == "refund":
        payment = Payment.objects.filter(errand=errand).first()
        if not payment:
            return Response({"error": "Payment not found for this errand"}, status=status.HTTP_404_NOT_FOUND)

        res = refund_payment(payment, reason=reason)
        refund = {
            "provider_refund_id": getattr(payment, "provider_refund_id", None),
            "provider_refund_status": getattr(payment, "provider_refund_status", None),
            "payment_reference": payment.reference,
            "amount": float(payment.amount_paid or payment.amount_expected),
        }
        return Response({"refund": refund, "result": res}, status=status.HTTP_200_OK)

    else:
        return Response({"error": "Unknown action"}, status=status.HTTP_400_BAD_REQUEST)


# ------------------ WEB (server-rendered) PAYMENT VIEWS ------------------ #
@login_required
def web_payments_list(request):
    payments = Payment.objects.filter(payer=request.user).order_by('-created_at')
    return render(request, "payments/list.html", {"payments": payments})


@login_required
def web_payment_detail(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    return render(request, "payments/detail.html", {"payment": payment})


@login_required
@csrf_protect
def web_initialize_payment(request):
    # optional errand_id passed via GET
    errand_id = request.GET.get("errand_id")

    # If an errand_id was provided, show a read-only page with VDA instructions
    # and ensure there is a pending Payment record for this errand & payer so
    # the sandbox simulate button can operate.
    if errand_id:
        try:
            errand = Errand.objects.get(id=errand_id)
        except Errand.DoesNotExist:
            messages.error(request, "Errand not found")
            return redirect("errands:list")

        # In sandbox/dev mode create or get a pending payment for this errand & payer
        payment, created = Payment.objects.get_or_create(
            payer=request.user,
            errand=errand,
            defaults={
                "reference": f"WEB-{uuid.uuid4().hex[:12].upper()}",
                "provider": "Paystack-Sandbox",
                "amount_expected": errand.price,
                "status": "pending",
            },
        )

        # Deposit instructions (platform VDA) from settings
        vda = getattr(settings, "PAYSTACK_DEPOSIT_INSTRUCTIONS", {})

        return render(request, "payments/initialize.html", {
            "errand": errand,
            "payment": payment,
            "vda": vda,
        })

    # POST fallback: keep existing initialize behavior if someone POSTs amount directly
    if request.method == "POST":
        errand_id = request.POST.get("errand_id")
        amount = request.POST.get("amount")
        if not errand_id or not amount:
            messages.error(request, "Errand and amount are required")
            return redirect(request.path)

        # create payment record (simulate initialize)
        reference = f"WEB-{uuid.uuid4().hex[:12].upper()}"
        payment = Payment.objects.create(
            payer=request.user,
            errand_id=errand_id,
            reference=reference,
            provider="Paystack-Sandbox",
            amount_expected=amount,
            status="pending",
        )
        messages.success(request, "Payment initialized. Use simulate to mark paid in sandbox.")
        return redirect(reverse("payment:web_payment_detail", args=[payment.id]))

    return render(request, "payments/initialize.html", {})


@login_required
@csrf_protect
def web_simulate_deposit(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    # Only allow payer to simulate deposit
    if payment.payer != request.user:
        messages.error(request, "Unauthorized")
        return redirect(reverse("payment:web_payment_detail", args=[payment.id]))

    payment.amount_paid = payment.amount_expected
    payment.status = "success"
    payment.paid_at = dj_timezone.now()
    payment.save()
    # mark associated errand visible
    try:
        if getattr(payment, "errand", None):
            payment.errand.status = "pending"
            payment.errand.save()
    except Exception:
        logger.exception("Failed to update errand after simulate_deposit")
    messages.success(request, "Payment simulated as paid (sandbox)")
    return redirect(reverse("payment:web_payment_detail", args=[payment.id]))


@login_required
@csrf_protect
def web_simulate_payout(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    # Only creator or admins can trigger payout in demo
    if request.user != payment.errand.creator:
        messages.error(request, "Only errand creator can trigger payout")
        return redirect(reverse("payment:web_payment_detail", args=[payment.id]))

    try:
        res = release_payment(payment)
        messages.success(request, "Payout simulated (sandbox)")
    except Exception as e:
        messages.error(request, f"Payout error: {e}")
    return redirect(reverse("payment:web_payment_detail", args=[payment.id]))


@login_required
@csrf_protect
def web_simulate_refund(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    # Only creator can refund their payment
    if request.user != payment.errand.creator:
        messages.error(request, "Only errand creator can trigger refund")
        return redirect(reverse("payment:web_payment_detail", args=[payment.id]))

    try:
        res = refund_payment(payment, reason="Sandbox refund via web")
        messages.success(request, "Refund simulated (sandbox)")
    except Exception as e:
        messages.error(request, f"Refund error: {e}")
    return redirect(reverse("payment:web_payment_detail", args=[payment.id]))