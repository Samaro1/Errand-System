from django.shortcuts import render,redirect
from django.urls import reverse
from django.contrib.auth import login, authenticate, logout
from .models import Customer, UserProfile
from django.http import HttpResponseRedirect, HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
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

@login_required
def verify(request):
    if request.method == "POST":
        user = request.user

        # Check if a profile already exists for this user, if it does, it will update
        profile, created = UserProfile.objects.get_or_create(user=user)

        # Update or create the profile fields with form data
        profile.fname = request.POST["fname"]
        profile.lname = request.POST["lname"]
        profile.email = request.POST["email"]
        profile.phone_num = request.POST["phone_num"]
        profile.bank_name = request.POST["bank_name"]
        profile.account_num = request.POST["account_num"]

        # Save the profile
        profile.save()

        return HttpResponse("Verified details saved successfully!")

    context = {
        "profile": profile,
        "is_new": created,
    }
    return render(request, "user/verify.html", context)

@login_required
def change_password(request):
    if request.method == "POST":
        old_password = request.POST.get("old_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        user = request.user

        # Check if old password matches
        if not user.check_password(old_password):
            messages.error(request, "Wrong old password.")
            return redirect("pwdreset")

        if new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
            return redirect("pwdreset")
        
        user.set_password(new_password)
        user.save()

        messages.success(request, "Password changed successfully. Please log in again.")
        logout(request)
        return redirect("login")

    return render(request, "passwordchange.html")