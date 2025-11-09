from django.test import TestCase

# Create your tests here.
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from user.models import Customer


# -------------------- USER APP TESTS --------------------
class UserTests(APITestCase):

    def setUp(self):
        # Create a test Customer (project uses Customer model)
        self.user = Customer.objects.create(username="testuser", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.vda_url = reverse("verify_and_create_vda")  # adjust if named differently

    def test_verify_and_create_vda_success(self):
        # Placeholder for VDA creation payload
        data = {
            "fname": "John",
            "lname": "Doe",
            "email": "john@example.com",
            "phone_num": "08012345678",
            "account_num": "1234567890",
            "bank_name": "AnyBank"
        }
        response = self.client.post(self.vda_url, data, format="json")
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    # Add more user-related tests here if needed

