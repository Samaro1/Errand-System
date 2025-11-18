from django.urls import path
from . import views

urlpatterns = [
    path("initialize/", views.initialize_payment, name="initialize_payment"),
    path("verify/<str:reference>/", views.verify_payment, name="verify_payment"),
    path("webhook/", views.paystack_webhook, name="paystack_webhook"),
    path("list/", views.list_payments, name="list_payments"),
    path("detail/<str:reference>/", views.payment_detail, name="payment_detail"),
    path("sandbox/operate/", views.sandbox_operate, name="sandbox_operate"),
    # API sandbox helpers (simulate deposit/payout/refund for a specific payment id)
    path("simulate/<int:payment_id>/deposit/", views.api_simulate_deposit, name="api_simulate_deposit"),
    path("simulate/<int:payment_id>/payout/", views.api_simulate_payout, name="api_simulate_payout"),
    path("simulate/<int:payment_id>/refund/", views.api_simulate_refund, name="api_simulate_refund"),
    # Web (server-rendered) payment pages
    path("web/initialize/", views.web_initialize_payment, name="web_initialize_payment"),
    path("web/list/", views.web_payments_list, name="web_payments_list"),
    path("web/<int:payment_id>/", views.web_payment_detail, name="web_payment_detail"),
    path("web/<int:payment_id>/simulate_pay/", views.web_simulate_deposit, name="web_simulate_deposit"),
    path("web/<int:payment_id>/simulate_payout/", views.web_simulate_payout, name="web_simulate_payout"),
    path("web/<int:payment_id>/simulate_refund/", views.web_simulate_refund, name="web_simulate_refund"),
]
