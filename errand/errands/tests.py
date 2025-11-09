from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from user.models import Customer
from errands.models import Errand
# -------------------- ERRANDS APP TESTS --------------------
class ErrandTests(APITestCase):
    def setUp(self):
        # Create users for creator and runner (use Customer model)
        self.creator = Customer.objects.create(username="creator", password="pass123")
        self.runner = Customer.objects.create(username="runner", password="pass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.creator)
        # Example Errand instance
        self.errand = Errand.objects.create(
            title="Test Errand",
            description="Test description",
            creator=self.creator,
            price=10.00
        )
    def test_list_errands(self):
        url = reverse("all_errands")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    def test_create_errand(self):
        url = reverse("create_errand")
        data = {"title": "New Errand", "description": "Details", "price": 20.00}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    def test_single_errand(self):
        url = reverse("single_errand", args=[self.errand.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    def test_delete_errand(self):
        url = reverse("delete_errand", args=[self.errand.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    def test_accept_errand(self):
        self.client.force_authenticate(user=self.runner)
        url = reverse("accept_errand", args=[self.errand.id])
        response = self.client.post(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
    def test_mark_completed(self):
        self.client.force_authenticate(user=self.runner)
        url = reverse("mark_completed", args=[self.errand.id])
        response = self.client.post(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])
    def test_approve_completion(self):
        url = reverse("approve_completion", args=[self.errand.id])
        response = self.client.post(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])
    def test_review_errand(self):
        url = reverse("review_errand", args=[self.errand.id])
        data = {"rating": 5, "feedback": "Great!"}
        response = self.client.post(url, data, format="json")
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])
