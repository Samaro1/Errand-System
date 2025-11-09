import os
import django
from django.urls import reverse

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'errand.settings')
django.setup()

from rest_framework.test import APIClient
from user.models import Customer
from rest_framework import status

client = APIClient()
user, _ = Customer.objects.get_or_create(username='dbguser', defaults={'password': 'pass'})
client.force_authenticate(user=user)

vda_url = reverse('verify_and_create_vda')
data = {
    'fname': 'John',
    'lname': 'Doe',
    'email': 'john@example.com',
    'phone_num': '08012345678',
    'account_num': '1234567890',
    'bank_name': 'AnyBank'
}

resp = client.post(vda_url, data, format='json')
print('STATUS:', resp.status_code)
try:
    print('CONTENT:', resp.json())
except Exception:
    print('RAW CONTENT:', resp.content)
