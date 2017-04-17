from django import forms
from django.core.exceptions import ValidationError
from .models import *
from django.utils.translation import ugettext, ugettext_lazy as _
from django.contrib.auth import forms as auth_forms, models as auth_models

from crispy_forms.helper import FormHelper
from crispy_forms import layout
from constance import config


class LoginForm(auth_forms.AuthenticationForm):
    username = forms.CharField(label="Email", max_length=30,
                               widget=forms.TextInput(attrs={'class': 'form-control', 'name': 'username'}))
    password = forms.CharField(label="Password", max_length=30,
                               widget=forms.TextInput(
                                   attrs={'class': 'form-control', 'name': 'password', 'type': 'password'}))


class PurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        exclude = ('invoice', )


class InvoicesCreateForm(forms.Form):
    users = forms.ModelMultipleChoiceField(queryset=User.objects.active().buyers().pay_themselves(),
                                           help_text="Select users to generate invoices for. Only users who pay themselves can be selected."
                                           )

    send_invoices = forms.BooleanField(required=False, initial=True,
                                       help_text="Whether to send invoice mails to the users' mail addresses. "
                                                 "Users who do not pay for themselves will get a notification of their "
                                                 "purchases instead of a real invoice. "
                                                 "If false, invoices will only be created internally.")

    send_payment_reminders = forms.BooleanField(required=False, initial=True,
                                                help_text="Whether to send payment reminder mails to users with an "
                                                          "account balance below {}".format(
                                                           currency(config.MAIL_BALANCE_SEND_MONEY)))

    def __init__(self, *args, **kwargs):
        super(InvoicesCreateForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.layout = layout.Layout(layout.Field('users', size="30"), 'send_invoices',
                                           'send_payment_reminders')

        self.helper.add_input(layout.Submit('create', 'Create'))
        self.helper.add_input(layout.Reset('reset', 'Unselect all'))


class UserCreateForm(auth_forms.UserCreationForm):
    class Meta:
        model = User
        fields = (
            'email', 'display_name', 'password1', 'password2', "purchases_paid_by_other", 'is_active', 'is_buyer',
            'is_favorite', 'is_admin')


class UserChangeWithPasswordForm(forms.ModelForm):
    """
    Mainly copied from auth.UserCreationForm, b/c UserChangeForm does not allow to change passwords
    This is still based on auth.models.User, but the model will be overwritten in another class
    """
    purchases_paid_by_other = forms.ModelChoiceField(queryset=User.objects.active().pay_themselves(),
                                                     help_text=User._meta.get_field(
                                                         'purchases_paid_by_other').help_text,
                                                     required=False)

    error_messages = {
        'password_mismatch': _("The two password fields didn't match."),
    }
    password1 = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput,
        required=False
    )
    password2 = forms.CharField(
        label=_("Password confirmation"),
        widget=forms.PasswordInput,
        strip=False,
        help_text=_("Enter the same password as before, for verification."),
        required=False
    )

    class Meta:
        model = auth_models.User
        fields = ("username",)
        field_classes = {'username': auth_forms.UsernameField}

    def __init__(self, *args, **kwargs):
        super(UserChangeWithPasswordForm, self).__init__(*args, **kwargs)
        if self._meta.model.USERNAME_FIELD in self.fields:
            self.fields[self._meta.model.USERNAME_FIELD].widget.attrs.update({'autofocus': ''})

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 or password2:
            if password1 and password2:
                if password1 != password2:
                    raise forms.ValidationError(
                        self.error_messages['password_mismatch'],
                        code='password_mismatch',
                    )
            # Validate only if at least one password was filled in
            auth_forms.password_validation.validate_password(self.cleaned_data.get('password2'), self.instance)
        self.instance.username = self.cleaned_data.get('username')
        return password2

    def save(self, commit=True):
        user = super(UserChangeWithPasswordForm, self).save(commit=False)

        # Only save passwords that were filled in!
        if self.cleaned_data["password1"]:
            user.set_password(self.cleaned_data["password1"])

        if commit:
            user.save()
        return user


class UserUpdateForm(UserChangeWithPasswordForm):
    class Meta:
        model = User
        fields = (
            'email', 'display_name', 'password1', 'password2', "purchases_paid_by_other", 'is_active', 'is_buyer',
            'is_favorite', 'is_admin')


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
            user = User.objects.active().buyers().get(pk=user_id)
            return user_id
        except User.DoesNotExist:
            raise ValidationError("Invalid user ID")

    quantity = forms.IntegerField()
    product_id = forms.IntegerField()
    user_id = forms.IntegerField()
    comment = forms.CharField(max_length=50, required=False)


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        exclude = ('',)


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        exclude = ('',)


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        exclude = ('',)


class StatsDisplayForm(forms.ModelForm):
    class Meta:
        model = StatsDisplay
        exclude = ('',)
