from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import Customer, UserProfile
from .serializers import CustomerSerializer, UserProfileSerializer
from django.db import transaction
from payment.utils import create_vda_account, PaystackAPIError

def get_tokens_for_user(user):
    """
    Generate JWT access and refresh tokens for a user.
    """
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


@api_view(["POST"])
@permission_classes([AllowAny])
def signup_view(request):
    """
    Register a new user (Customer) and return JWT tokens
    """
    serializer = CustomerSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        tokens = get_tokens_for_user(user)
        return Response(
            {
                "message": "Signup successful",
                "user": CustomerSerializer(user).data,
                "tokens": tokens,
            },
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    """
    Log in an existing user and return JWT tokens
    """
    username = request.data.get("username")
    password = request.data.get("password")
    user = authenticate(request, username=username, password=password)

    if user is not None:
        tokens = get_tokens_for_user(user)
        return Response(
            {
                "message": "Login successful",
                "user": CustomerSerializer(user).data,
                "tokens": tokens,
            },
            status=status.HTTP_200_OK
        )
    return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify_user(request):
    """
    Create or update user profile (verification step)
    """
    user = request.user
    profile, created = UserProfile.objects.get_or_create(user=user)

    serializer = UserProfileSerializer(profile, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(
            {
                "message": "Verification details saved successfully",
                "profile": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change user password securely
    """
    old_password = request.data.get("old_password")
    new_password = request.data.get("new_password")
    confirm_password = request.data.get("confirm_password")

    user = request.user

    if not user.check_password(old_password):
        return Response({"error": "Incorrect old password"}, status=status.HTTP_400_BAD_REQUEST)

    if new_password != confirm_password:
        return Response({"error": "New passwords do not match"}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save()

    return Response({"message": "Password changed successfully. Please log in again."}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_and_create_vda(request):
    """
    Verify the authenticated user's profile and create a Paystack VDA (Virtual Dedicated Account).
    - Requires: fname, lname, email, phone_num
    - Links the created VDA to the user's profile.
    """
    user = request.user
    # ensure user context exists

    # Ensure the user has an associated profile (create if missing),
    # then validate and update the user's profile data
    profile, _ = UserProfile.objects.get_or_create(user=user)
    serializer = UserProfileSerializer(profile, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response({"error": "Invalid input data", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            profile = serializer.save()

            # Make sure the user has the required fields for VDA creation
            missing_fields = [f for f in ["fname", "lname", "email", "phone_num"] if not getattr(profile, f, None)]
            if missing_fields:
                return Response(
                    {"error": f"Missing required profile fields: {', '.join(missing_fields)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Call Paystack to create the virtual account
            vda_data = create_vda_account(profile)

            # Update the user's profile with Paystack VDA details
            profile.vda_account_number = vda_data.get("account_number")
            profile.vda_bank_name = vda_data.get("bank_name")
            profile.vda_account_name = vda_data.get("account_name")
            profile.vda_reference = vda_data.get("reference")
            profile.save()

        return Response({
            "message": "User verified and VDA created successfully",
            "vda_details": {
                "account_name": profile.vda_account_name,
                "account_number": profile.vda_account_number,
                "bank_name": profile.vda_bank_name,
                "reference": profile.vda_reference,
            }
        }, status=status.HTTP_201_CREATED)

    except PaystackAPIError as e:
        return Response(
            {"error": f"Paystack API Error: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY  # 502 → bad upstream service
        )

    except Exception as e:
        return Response(
            {"error": f"Internal Server Error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )