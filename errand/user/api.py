from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import UserProfile

@login_required
def get_user_profile(request):
    user = request.user
    try:
        profile = UserProfile.objects.get(user=user)
        return JsonResponse({
            "fname": profile.fname,
            "lname": profile.lname,
            "email": profile.email,
            "phone_num": profile.phone_num,
            "bank_name": profile.bank_name,
            "account_num": profile.account_num
        })
    except UserProfile.DoesNotExist:
        return JsonResponse({"error": "Profile not found"}, status=404)

