from django.db import models
from django.contrib.auth.models import User


# Create your models here.
class Product(models.Model):
    seller=models.ForeignKey(User,on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=100)
    price = models.FloatField()
    File = models.FileField(upload_to='uploads')
    image = models.ImageField(upload_to='images',blank=True)
    total_sales_amount=models.FloatField(default=0)
    total_sales=models.IntegerField(default=0)

    def __str__(self):
        return self.name

class orderDetail(models.Model):
    customer_email=models.EmailField()
    product=models.ForeignKey(Product,on_delete=models.CASCADE)
    amount=models.IntegerField()
    stripe_checkout_session_id=models.CharField(max_length=200,blank=True)
    stripe_payment_intent=models.CharField(max_length=200,blank=True)
    has_paid=models.BooleanField(default=False)
    created_on=models.DateTimeField(auto_now_add=True)
    updated_on=models.DateTimeField(auto_now=True)