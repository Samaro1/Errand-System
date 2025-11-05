from rest_framework import serializers
from .models import Customer, UserProfile


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'username', 'password']
        extra_kwargs = {
            'password': {'write_only': True}  # no password return in API response
        }

    # Add validation for password strength or uniqueness later
    def create(self, validated_data):
        """Custom create method to hash password when saving"""
        password = validated_data.pop('password', None)
        user = Customer(**validated_data)
        if password:
            user.password = password  #I should replace with a hashing method
        user.save()
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())

    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'account_num', 'bank_name', 
            'fname', 'lname', 'email', 'phone_num'
        ]
