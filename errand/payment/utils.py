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


def release_payment(payment):
    """Mark a payment as released/transferred to the errand runner.

    This is a simplified implementation for the school project: in a real
    system you'd call the payment provider's transfer API to move funds to the
    runner's VDA/bank account. Here we update the payment record to reflect
    a completed transfer.
    """
    # If already refunded, skip
    if payment.refunded:
        return {"status": "skipped", "reason": "already_refunded"}

    # Simulate transfer in test or debug mode
    import sys
    fake_flag = getattr(settings, "PAYSTACK_FAKE_IN_TESTS", False)
    if fake_flag or getattr(settings, "DEBUG", False) or "test" in sys.argv:
        payment.recipient_vda = payment.errand.runner.userprofile.vda_account_number if hasattr(payment.errand.runner, 'userprofile') else None
        payment.status = "success"
        from django.utils import timezone
        payment.paid_at = timezone.now()
        payment.save()
        return {"status": "ok", "reference": payment.reference}

    # Live mode: perform real transfer via Paystack
    # Steps:
    # 1. Resolve bank code for runner's bank name
    # 2. Create a transfer recipient (type 'nuban')
    # 3. Initiate a transfer to recipient
    from decimal import Decimal
    from django.utils import timezone

    secret = getattr(settings, "PAYSTACK_SECRET_KEY", None)
    base = getattr(settings, "PAYSTACK_BASE_URL", "https://api.paystack.co")
    if not secret:
        raise PaystackAPIError("PAYSTACK_SECRET_KEY not configured")

    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
    }

    # runner profile and bank details
    profile = getattr(payment.errand.runner, "userprofile", None)
    if not profile:
        raise PaystackAPIError("Runner has no user profile with bank details")

    bank_name = profile.bank_name
    account_number = profile.account_num
    account_name = f"{profile.fname} {profile.lname}"

    # 1) get bank list and find bank code
    # Prefer stored bank_code or recipient_code on profile to avoid full bank list lookup
    bank_code = getattr(profile, "bank_code", None)
    recipient_code = getattr(profile, "paystack_recipient_code", None)

    if not bank_code and not recipient_code:
        banks_url = f"{base}/bank"
        resp = requests.get(banks_url, headers=headers)
        try:
            banks_data = resp.json()
        except Exception:
            raise PaystackAPIError("Failed to retrieve bank list from Paystack")

        if not banks_data.get("status"):
            # Some endpoints may return status=False on failure
            raise PaystackAPIError(f"Paystack bank list error: {banks_data.get('message')}")

        bank_list = banks_data.get("data") or []
        for b in bank_list:
            if bank_name.lower() in b.get("name", "").lower() or b.get("name", "").lower() in bank_name.lower():
                bank_code = b.get("code")
                break

    # If we still don't have a bank code and no recipient, bail out
    if not bank_code and not recipient_code:
        raise PaystackAPIError(f"Could not find bank code for bank: {bank_name}")
    try:
        banks_data = resp.json()
    except Exception:
        raise PaystackAPIError("Failed to retrieve bank list from Paystack")

    if not banks_data.get("status"):
        # Some endpoints may return status=False on failure
        raise PaystackAPIError(f"Paystack bank list error: {banks_data.get('message')}")

    bank_list = banks_data.get("data") or []
    bank_code = None
    for b in bank_list:
        if bank_name.lower() in b.get("name", "").lower() or b.get("name", "").lower() in bank_name.lower():
            bank_code = b.get("code")
            break

    if not bank_code:
        raise PaystackAPIError(f"Could not find bank code for bank: {bank_name}")

    # 2) create transfer recipient
    # Create recipient only if we don't already have one
    recipient_code = recipient_code
    if not recipient_code:
        recip_payload = {
            "type": "nuban",
            "name": account_name,
            "account_number": account_number,
            "bank_code": bank_code,
            "currency": payment.currency or "NGN",
        }
        recip_url = f"{base}/transferrecipient"
        r = requests.post(recip_url, json=recip_payload, headers=headers)
        try:
            rdata = r.json()
        except Exception:
            raise PaystackAPIError("Failed to parse transfer recipient response")

        if not rdata.get("status"):
            raise PaystackAPIError(f"Transfer recipient creation failed: {rdata.get('message')}")

        recipient_code = rdata.get("data", {}).get("recipient_code")
        # persist recipient_code and bank_code for future reuse
        try:
            profile.paystack_recipient_code = recipient_code
            if bank_code:
                profile.bank_code = bank_code
            profile.save()
        except Exception:
            # Non-fatal: we still proceed with transfer even if we can't persist
            pass
    try:
        rdata = r.json()
    except Exception:
        raise PaystackAPIError("Failed to parse transfer recipient response")

    if not rdata.get("status"):
        raise PaystackAPIError(f"Transfer recipient creation failed: {rdata.get('message')}")

    recipient_code = rdata.get("data", {}).get("recipient_code")
    if not recipient_code:
        raise PaystackAPIError("No recipient_code returned by Paystack")

    # 3) initiate transfer
    amt = payment.amount_paid or payment.amount_expected or Decimal("0.00")
    amount_kobo = int(Decimal(amt) * 100)
    transfer_payload = {
        "source": "balance",
        "amount": amount_kobo,
        "recipient": recipient_code,
        "reason": f"Payout for errand {payment.errand.id}",
    }
    transfer_url = f"{base}/transfer"
    t = requests.post(transfer_url, json=transfer_payload, headers=headers)
    try:
        tdata = t.json()
    except Exception:
        raise PaystackAPIError("Failed to parse transfer response")

    if not tdata.get("status"):
        raise PaystackAPIError(f"Transfer failed: {tdata.get('message')}")

    # update local payment record
    payment.recipient_vda = recipient_code
    payment.provider_transfer_id = tdata.get("data", {}).get("id") or tdata.get("data", {}).get("transfer_code")
    payment.provider_transfer_status = tdata.get("data", {}).get("status")
    payment.status = "success"
    payment.paid_at = timezone.now()
    payment.save()
    return {"status": "ok", "reference": payment.reference, "transfer": tdata.get("data")}


def refund_payment(payment, reason=None):
    """Mark a payment as refunded.

    For tests and development this simply updates the payment record. In
    production you'd call the provider's refund API and verify the refund
    completed before updating local state.
    """
    if payment.refunded:
        return {"status": "skipped", "reason": "already_refunded"}

    import sys
    fake_flag = getattr(settings, "PAYSTACK_FAKE_IN_TESTS", False)
    if fake_flag or getattr(settings, "DEBUG", False) or "test" in sys.argv:
        payment.status = "refunded"
        payment.refunded = True
        payment.refund_reason = reason
        payment.save()
        return {"status": "ok", "reference": payment.reference}

    # Live refund path using Paystack refund API (suitable for sandbox testing)
    secret = getattr(settings, "PAYSTACK_SECRET_KEY", None)
    base = getattr(settings, "PAYSTACK_BASE_URL", "https://api.paystack.co")
    if not secret:
        raise PaystackAPIError("PAYSTACK_SECRET_KEY not configured")

    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
    }

    # Prefer to refund by transaction reference if available
    refund_payload = {"reference": payment.reference}
    # If amount specified, send amount in kobo
    if payment.amount_paid:
        from decimal import Decimal
        refund_payload["amount"] = int(Decimal(payment.amount_paid) * 100)

    refund_url = f"{base}/refund"
    r = requests.post(refund_url, json=refund_payload, headers=headers)
    try:
        rdata = r.json()
    except Exception:
        raise PaystackAPIError("Failed to parse refund response")

    if not rdata.get("status"):
        raise PaystackAPIError(f"Refund failed: {rdata.get('message')}")

    # store refund info
    refund_id = rdata.get("data", {}).get("id") or rdata.get("data", {}).get("reference")
    refund_status = rdata.get("data", {}).get("status")

    payment.status = "refunded"
    payment.refunded = True
    payment.refund_reason = reason
    payment.provider_refund_id = refund_id
    payment.provider_refund_status = refund_status
    payment.save()

    return {"status": "ok", "reference": payment.reference, "refund": rdata.get("data")}