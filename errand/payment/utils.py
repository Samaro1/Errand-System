# payment/utils.py
import requests
from django.conf import settings
from .models import Payment
from datetime import datetime

# Example using Paystack (you can replace this with your real provider)
PAYSTACK_BASE_URL = "https://api.paystack.co"
HEADERS = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}

def create_vda_account(user):
    """
    Create a Virtual Dedicated Account (VDA) for a user.
    This example assumes you are using Monnify or a similar provider.
    """

    url = "https://sandbox.monnify.com/api/v1/bank-transfer/reserved-accounts"  # example endpoint

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.MONNIFY_API_KEY}"  # or token if you authenticate separately
    }

    payload = {
        "accountReference": f"user_{user.id}_vda",
        "accountName": f"{user.first_name} {user.last_name}",
        "currencyCode": "NGN",
        "contractCode": settings.MONNIFY_CONTRACT_CODE,
        "customerEmail": user.email,
        "bvn": user.profile.bvn if hasattr(user, "profile") else None,
        "getAllAvailableBanks": False,
        "preferredBanks": ["Providus Bank"]  # optional
    }

    response = requests.post(url, json=payload, headers=headers)
    data = response.json()

    if response.status_code == 200 and data.get("requestSuccessful"):
        return {
            "accountNumber": data["responseBody"]["accountNumber"],
            "accountName": data["responseBody"]["accountName"],
            "bankName": data["responseBody"]["bankName"],
        }
    else:
        raise Exception(f"Failed to create VDA: {data}")
    
    
def initialize_payment(amount, email, reference):
    """Initialize a payment and return the authorization URL."""
    url = f"{PAYSTACK_BASE_URL}/transaction/initialize"
    payload = {
        "amount": int(amount * 100),  # Paystack expects amount in kobo
        "email": email,
        "reference": reference,
        "callback_url": f"{settings.FRONTEND_URL}/payment/verify/{reference}",
    }

    response = requests.post(url, json=payload, headers=HEADERS)
    response_data = response.json()

    if response.status_code == 200 and response_data.get("status"):
        return response_data["data"]["authorization_url"]
    else:
        raise Exception(response_data.get("message", "Payment initialization failed"))


def verify_payment(reference):
    """Verify payment status with Paystack using the reference."""
    url = f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}"
    response = requests.get(url, headers=HEADERS)
    response_data = response.json()

    if response.status_code == 200 and response_data.get("status"):
        data = response_data["data"]

        # update local record if it exists
        try:
            payment = Payment.objects.get(reference=reference)
            payment.status = "success" if data["status"] == "success" else "failed"
            payment.amount_paid = data["amount"] / 100  # convert from kobo
            payment.payment_channel = data["channel"]
            payment.paid_at = datetime.strptime(data["paid_at"], "%Y-%m-%dT%H:%M:%S.%fZ")
            payment.save()
        except Payment.DoesNotExist:
            pass

        return data
    else:
        raise Exception(response_data.get("message", "Payment verification failed"))


def handle_webhook_event(payload):
    """Handle payment provider webhook events."""
    event = payload.get("event")
    data = payload.get("data")

    if not data:
        return "Invalid payload"

    reference = data.get("reference")
    try:
        payment = Payment.objects.get(reference=reference)
    except Payment.DoesNotExist:
        return "Payment record not found"

    if event == "charge.success":
        payment.status = "success"
        payment.amount_paid = data["amount"] / 100
        payment.payment_channel = data.get("channel", "webhook")
        payment.paid_at = datetime.strptime(data["paid_at"], "%Y-%m-%dT%H:%M:%S.%fZ")
        payment.save()
    elif event == "charge.failed":
        payment.status = "failed"
        payment.save()

    return f"Webhook handled for event {event}"
