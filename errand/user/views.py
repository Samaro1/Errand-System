from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import Customer, UserProfile
from .serializers import CustomerSerializer, UserProfileSerializer
from payment.utils import create_vda_account


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
    API endpoint for user verification and VDA account creation.
    """
    data = request.data
    required_fields = ['fname', 'lname', 'email', 'phone_num', 'account_num', 'bank_name']

    for field in required_fields:
        if field not in data or not data[field]:
            return Response({"error": f"{field} is required"}, status=status.HTTP_400_BAD_REQUEST)

    user = request.user
    try:
        profile, created = UserProfile.objects.update_or_create(
            user=user,
            defaults={
                "fname": data["fname"],
                "lname": data["lname"],
                "email": data["email"],
                "phone_num": data["phone_num"],
                "account_num": data["account_num"],
                "bank_name": data["bank_name"],
            }
        )

        vda_data = create_vda_account(profile)

        if not vda_data:
            return Response({"error": "Failed to create VDA account"}, status=status.HTTP_400_BAD_REQUEST)

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

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)