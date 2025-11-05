from django.urls import path
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
)
from . import views

urlpatterns = [
    # Authentication routes
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('change-password/', views.change_password, name='change_password'),

    # User verification and VDA
    path('verify-user/', views.verify_user, name='verify_user'),
    path('verify-vda/', views.verify_and_create_vda, name='verify_and_create_vda'),

    # JWT utility routes
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
]
