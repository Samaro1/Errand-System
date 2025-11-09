from django.test import TestCase

# Create your tests here.
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from user.models import Customer
from errands.models import Errand
from payment.models import Payment


# -------------------- PAYMENT APP TESTS --------------------
class PaymentTests(APITestCase):

    def setUp(self):
        # Use Customer model for tests so foreign keys match project models
        self.user = Customer.objects.create(username="payer", password="pass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Example Errand and Payment
        self.errand = Errand.objects.create(
            title="Payment Errand",
            description="Payment description",
            creator=self.user,
            price=100.00
        )
        self.payment = Payment.objects.create(
            payer=self.user,
            errand=self.errand,
            reference="TESTREF123",
            amount_expected=1000.00,
            status="pending"
        )

    def test_initialize_payment(self):
        url = reverse("initialize_payment")
        data = {"errand_id": self.errand.id, "amount": 1000.00}
        response = self.client.post(url, data, format="json")
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_verify_payment(self):
        url = reverse("verify_payment", args=[self.payment.reference])
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND])

    def test_list_payments(self):
        url = reverse("list_payments")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_payment_detail(self):
        url = reverse("payment_detail", args=[self.payment.reference])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_paystack_webhook(self):
        url = reverse("paystack_webhook")
        # Example webhook payload
        data = {
            "event": "payment.success",
            "data": {
                "reference": self.payment.reference,
                "amount": 100000,
                "authorization": {
                    "bank": "TestBank",
                    "last4": "1234"
                }
            }
        }
        response = self.client.post(url, data, format="json")
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
