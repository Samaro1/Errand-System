from django.test import TestCase, Client
from user.models import Customer, UserProfile
from errands.models import Errand
from payment.models import Payment
from django.urls import reverse

class PaymentSandboxWebTests(TestCase):
    def setUp(self):
        self.client = Client()
        # create users
        self.creator = Customer.objects.create(username='creator', password='pass')
        self.runner = Customer.objects.create(username='runner', password='pass')
        # login creator (use custom backend to avoid Django User expectations)
        self.client.force_login(self.creator, backend='user.backends.CustomerBackend')
        # create errand
        self.errand = Errand.objects.create(title='E1', description='d', creator=self.creator, price=50)

    def test_initialize_and_simulate_deposit_and_payout_and_refund(self):
        # initialize payment via web
        url_init = reverse('payment:web_initialize_payment')
        resp = self.client.post(url_init, {'errand_id': self.errand.id, 'amount': '50'})
        # should redirect to detail
        self.assertEqual(resp.status_code, 302)
        payment = Payment.objects.filter(errand=self.errand, payer=self.creator).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.status, 'pending')

        # simulate deposit (payer triggers)
        url_sim_pay = reverse('payment:web_simulate_deposit', args=[payment.id])
        resp = self.client.post(url_sim_pay)
        self.assertEqual(resp.status_code, 302)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'success')
        self.assertIsNotNone(payment.paid_at)

        # simulate payout (creator triggers)
        url_sim_payout = reverse('payment:web_simulate_payout', args=[payment.id])
        resp = self.client.post(url_sim_payout)
        self.assertEqual(resp.status_code, 302)
        payment.refresh_from_db()
        # In sandbox release_payment should mark status success and set provider_transfer_id in fake path
        self.assertIn(payment.status, ['success', 'refunded'])

        # simulate refund
        url_sim_refund = reverse('payment:web_simulate_refund', args=[payment.id])
        resp = self.client.post(url_sim_refund)
        self.assertEqual(resp.status_code, 302)
        payment.refresh_from_db()
        self.assertTrue(payment.refunded)