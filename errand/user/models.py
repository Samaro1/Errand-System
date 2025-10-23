from django.db import models

# Create your models here.
class Customer(models.Model):
    fname= models.CharField(max_length=30, null= True, blank= True)
    lname=  models.CharField(max_length=30, null= True, blank=True)
    username= models.CharField(max_length= 20)
    email= models.EmailField(null= True, blank= True)
    phone_num= models.CharField(max_length= 11, null=True, blank=True)
    password= models.CharField()
    account_num= models.CharField(max_length=10, blank=True,null=True)
    bank_name= models.CharField(blank=True, null=True)

    def  __str__(self):
        return f"User {self.first} {self.last} phone number: {self.phone_num}"
    

