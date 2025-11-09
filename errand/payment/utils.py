# payment/utils.py
import requests
from django.conf import settings
from .models import Payment
from datetime import datetime

# Example using Paystack (you can replace this with your real provider)
PAYSTACK_BASE_URL = "https://api.paystack.co"
HEADERS = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}

# payment/utils.py
import requests
from django.conf import settings

class PaystackAPIError(Exception):
    """Custom exception for Paystack API errors"""
    pass

def create_vda_account(user_profile):
    """
    Create a Virtual Deposit Account (VDA) on Paystack for a user.
    Args:
        user_profile: UserProfile instance containing fname, lname, email.
    Returns:
        dict: VDA account details (account_number, bank_name, account_name, reference)
    Raises:
        PaystackAPIError: If the API request fails.
    """
    # Short-circuit Paystack calls when configured to do so. Prefer the explicit
    # settings flag `PAYSTACK_FAKE_IN_TESTS`. For backwards compatibility we also
    # allow DEBUG=True or running under the test runner ("test" in sys.argv) to
    # enable the fake path.
    import sys
    fake_flag = getattr(settings, "PAYSTACK_FAKE_IN_TESTS", False)
    if fake_flag or getattr(settings, "DEBUG", False) or "test" in sys.argv:
        return {
            "account_number": "0000000000",
            "bank_name": "TestBank",
            "account_name": f"{user_profile.fname} {user_profile.lname}",
            "reference": "TESTVDA123",
        }

    url = f"{settings.PAYSTACK_BASE_URL}/virtual-account-numbers"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "customer": {
            "name": f"{user_profile.fname} {user_profile.lname}",
            "email": user_profile.email
        },
        "preferred_bank": "all"  # Let Paystack pick a bank automatically
    }

    response = requests.post(url, json=payload, headers=headers)
    data = response.json()

    if not data.get("status"):
        raise PaystackAPIError(f"Paystack error: {data.get('message')}")

    account_info = data.get("data", {})
    return {
        "account_number": account_info.get("account_number"),
        "bank_name": account_info.get("bank_name"),
        "account_name": account_info.get("account_name"),
        "reference": account_info.get("reference")
    }
    
    
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