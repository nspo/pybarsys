from django import forms
from django.core.exceptions import ValidationError
from .models import Product, User


class SingleUserSinglePurchaseForm(forms.Form):
    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]

        if quantity < 1:
            raise ValidationError("Invalid quantity")
        else:
            return quantity

    def clean_product_id(self):
        product_id = self.cleaned_data["product_id"]
        try:
            product = Product.objects.get(pk=product_id)
            return product_id
        except Product.DoesNotExist:
            raise ValidationError("Invalid product ID")

    def clean_user_id(self):
        user_id = self.cleaned_data["user_id"]
        try:
            user = User.objects.get(pk=user_id) # more needed
            return user_id
        except User.DoesNotExist:
            raise ValidationError("Invalid user ID")

    quantity = forms.IntegerField()
    product_id = forms.IntegerField()
    user_id = forms.IntegerField()


