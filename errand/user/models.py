from django.db import models

# Create your models here.

class Customer(models.Model):
    username = models.CharField(max_length=20, unique=True)
    #To be hashed later
    password = models.CharField(max_length=128)
    # minimal fields to interoperate with Django auth utilities used by sessions
    last_login = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.username
    
    @property
    def is_authenticated(self):
        """Simple compatibility for DRF/Django permission checks in tests."""
        return True

    @property
    def is_anonymous(self):
        return False


class UserProfile(models.Model):
    user = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name="profile")
    account_num= models.CharField(max_length=10, blank=False,null=False)
    bank_name= models.CharField(blank=False,null=False)
    fname= models.CharField(max_length=30,blank=False,null=False)
    lname=  models.CharField(max_length=30,blank=False,null=False)
    email= models.EmailField(blank=False,null=False)
    phone_num= models.CharField(max_length= 11, blank=False,null=False)

    # Persisted bank and provider fields to avoid repeated lookups
    bank_code = models.CharField(max_length=20, blank=True, null=True)
    paystack_recipient_code = models.CharField(max_length=100, blank=True, null=True)

    # VDA (Virtual Dedicated Account) fields
    vda_account_number = models.CharField(max_length=20, blank=True, null=True)
    vda_bank_name = models.CharField(max_length=100, blank=True, null=True)
    vda_account_name = models.CharField(max_length=100, blank=True, null=True)
    vda_reference = models.CharField(max_length=50, blank=True, null=True)  # Paystack's VDA reference ID


    def __str__(self):
        return f"{self.user.username} Profile"