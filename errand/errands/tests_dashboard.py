from django.urls import reverse
from django.test import TestCase, Client
from rest_framework.test import APIClient
from user.models import Customer
from errands.models import Errand
from payment.models import Payment


class DashboardTests(TestCase):
    def setUp(self):
        # Users
        self.creator = Customer.objects.create(username="creator", password="pass123")
        self.runner = Customer.objects.create(username="runner", password="pass123")
        # clients
        self.api_client = APIClient()
        self.web_client = Client()
        # login web client
        self.web_client.force_login(self.creator)
        # API client will auth where needed by force_authenticate
        self.api_client.force_authenticate(user=self.creator)

    def test_root_redirects_authenticated_to_dashboard(self):
        # Authenticated browser should be redirected to dashboard by default
        resp = self.web_client.get(reverse('root_dispatch'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('errands:dashboard'), resp.url)

    def test_payment_creates_visibility_and_refund(self):
        # Create an errand in payment_pending status (created but not yet posted)
        err = Errand.objects.create(
            creator=self.creator,
            title="Pay me to post",
            description="testing payment flow",
            price=50.00,
            status="payment_pending",
        )

        # Simulate sandbox pay via API (sandbox_operate)
        url = reverse('sandbox_operate')
        payload = {"action": "pay", "errand_id": err.id, "amount": 50.00}
        resp = self.api_client.post(url, payload, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('receipt', data)

        # Ensure a Payment object exists and is marked success
        payment = Payment.objects.filter(errand=err).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.status, 'success')
        self.assertFalse(payment.refunded)

        # Errand should now be visible (status == pending)
        err.refresh_from_db()
        self.assertEqual(err.status, 'pending')

        # The dashboard page should list the errand title for the creator
        dash = self.web_client.get(reverse('errands:dashboard'))
        self.assertContains(dash, err.title)

        # Now simulate a refund
        refund_payload = {"action": "refund", "errand_id": err.id}
        r2 = self.api_client.post(url, refund_payload, format='json')
        self.assertEqual(r2.status_code, 200)
        rdata = r2.json()
        self.assertIn('refund', rdata)

        # Refresh payment and assert refunded flag
        payment.refresh_from_db()
        self.assertTrue(payment.refunded)
        self.assertEqual(payment.status, 'refunded')

        # Dashboard still accessible; and payments can be viewed via payments page
        dash2 = self.web_client.get(reverse('errands:dashboard'))
        self.assertEqual(dash2.status_code, 200)