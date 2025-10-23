from django.shortcuts import render,redirect
from django.urls import reverse
from django.contrib.auth import login, authenticate
from .models import Customer
from django.http import HttpResponseRedirect, HttpResponse

# Create your views here.
def signup_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]

        user = Customer.objects.create_user(username= username, password= password)
        login(request,user)
        return redirect("verify")
    else:
        return render(request, "user/signup.html")

def login_view(request):
    if request.method == "POST":
        user= request.user
        username= request.POST["username"]
        password= request.POST["password"]

        user= authenticate(request, username= username, password= password)
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))
        else:
            return render (request, "user/login.html",{
                "message": "Invalid credentials."})
    else:
        return render(request, "user/login.html")

def verify(request):
    if not request.user.is_authenticated:
        return redirect("login")
    
    if request.method == "POST":
        user=request.user

        user.fname = request.POST["fname"]
        user.lname= request.POST["lname"]
        user.email= request.POST["email"]
        user.phone_num= request.POST["phone_num"]
        user.bank_name= request.POST["bank_name"]
        user.account_num= request.POST["account_num"]
        user.save()

        return HttpResponse("Success")