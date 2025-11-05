from django.urls import path
from . import views

urlpatterns = [
    path("api/signup/", views.signup_view, name="signup"),       
    path("api/login/", views.login_view, name="login"),            
    path("api/verify/", views.verify, name="verify"),              
    path("api/change-password/", views.change_password, name="pwdreset"), 
]
