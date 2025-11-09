from django.urls import path
from . import views

urlpatterns = [
    path("initialize/", views.initialize_payment, name="initialize_payment"),
    path("verify/<str:reference>/", views.verify_payment, name="verify_payment"),
    path("webhook/", views.paystack_webhook, name="paystack_webhook"),
    path("list/", views.list_payments, name="list_payments"),
    path("detail/<str:reference>/", views.payment_detail, name="payment_detail"),
    path("sandbox/operate/", views.sandbox_operate, name="sandbox_operate"),
]
