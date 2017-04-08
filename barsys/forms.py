from django import forms
from django.core.exceptions import ValidationError
from .models import *
from django.contrib.auth.forms import AuthenticationForm




class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Username", max_length=30,
                               widget=forms.TextInput(attrs={'class': 'form-control', 'name': 'username'}))
    password = forms.CharField(label="Password", max_length=30,
                               widget=forms.TextInput(
                                   attrs={'class': 'form-control', 'name': 'password', 'type': 'password'}))


class PurchaseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(PurchaseForm, self).__init__(*args, **kwargs)

        # change widget attributes
        self.fields['invoice'].widget.attrs["disabled"] = True

    class Meta:
        model = Purchase
        fields = ('user', 'product_name', 'product_category', 'product_price', 'product_amount', 'quantity', 'invoice')


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
            user = User.objects.get(pk=user_id, is_active=True, is_buyer=True)
            return user_id
        except User.DoesNotExist:
            raise ValidationError("Invalid user ID")

    quantity = forms.IntegerField()
    product_id = forms.IntegerField()
    user_id = forms.IntegerField()
