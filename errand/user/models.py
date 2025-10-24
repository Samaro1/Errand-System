from django.db import models

# Create your models here.

class Customer(models.Model):
    username = models.CharField(max_length=20, unique=True)
    #To be hashed later
    password = models.CharField(max_length=128)

    def __str__(self):
        return self.username


class UserProfile(models.Model):
    user = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name="profile")
    account_num= models.CharField(max_length=10, blank=False,null=False)
    bank_name= models.CharField(blank=False,null=False)
    fname= models.CharField(max_length=30,blank=False,null=False)
    lname=  models.CharField(max_length=30,blank=False,null=False)
    email= models.EmailField(blank=False,null=False)
    phone_num= models.CharField(max_length= 11, blank=False,null=False)
