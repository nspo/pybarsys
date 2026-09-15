import re

from crispy_forms import layout
from crispy_forms.helper import FormHelper
from django import forms
from django.contrib.auth import forms as auth_forms
from django.utils.translation import gettext_lazy as _

from .models import *
from pybarsys.settings import PybarsysPreferences


class LoginForm(auth_forms.AuthenticationForm):
    username = forms.CharField(
        label="Email",
        max_length=30,
        widget=forms.TextInput(attrs={"class": "form-control", "name": "username"}),
    )
    password = forms.CharField(
        label="Password",
        max_length=30,
        widget=forms.TextInput(
            attrs={"class": "form-control", "name": "password", "type": "password"}
        ),
    )


class PurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        exclude = ("invoice",)


class ProductAutochangeForm(forms.ModelForm):
    class Meta:
        model = ProductAutochange
        fields = ["product", "change_active", "change_bold", "set_price"]

    def __init__(self, *args, **kwargs):
        # get manually added parent reference (sometimes this is strangely called without one)
        parent = kwargs.pop("parent") if "parent" in kwargs else None

        super(ProductAutochangeForm, self).__init__(*args, **kwargs)

        if self.instance.pk:
            pass
        else:
            if parent and parent.pk:
                # if this is a new ProductAutochange, then exclude all products that
                # already have been selected in the parent PASet
                self.fields["product"].queryset = Product.objects.exclude(
                    pk__in=parent.products.all()
                )

        self.helper = FormHelper()
        self.helper.template = "bootstrap3/table_inline_formset.html"
        self.helper.form_tag = False


class ProductAutochangeInlineFormSet(
    forms.inlineformset_factory(
        ProductAutochangeSet, ProductAutochange, form=ProductAutochangeForm, extra=1
    )
):
    def get_form_kwargs(self, index):
        kwargs = super(ProductAutochangeInlineFormSet, self).get_form_kwargs(index)
        kwargs.update({"parent": self.instance})
        return kwargs

    def clean(self):
        super(ProductAutochangeInlineFormSet, self).clean()

        product_pks = []
        num_productautochanges = 0
        for form in self.forms:
            if not form.is_valid():
                continue  # do not return yet b/c otherwise user could delete the last PAc if it's invalid
            if form.cleaned_data and not form.cleaned_data.get("DELETE"):
                num_productautochanges += 1
                if form.cleaned_data["product"].pk in product_pks:
                    form.add_error(
                        "product",
                        "Product {} cannot be autochanged multiple times.".format(
                            form.cleaned_data["product"]
                        ),
                    )
                else:
                    product_pks.append(form.cleaned_data["product"].pk)

        if num_productautochanges < 1:
            form.add_error(
                None,
                ValidationError("At least one product autochange needs to be defined."),
            )


class ProductAutochangeSetForm(forms.ModelForm):
    class Meta:
        model = ProductAutochangeSet
        fields = ("title", "description", "change_others_active", "change_others_bold")

    def __init__(self, *args, **kwargs):
        super(ProductAutochangeSetForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_tag = False


class InvoicesCreateForm(forms.Form):
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.active().buyers().pay_themselves(),
        help_text="Select users to generate invoices for. Only users who pay themselves can be selected.",
    )

    send_invoices = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Whether to send invoice mails to the users' mail addresses. "
        "If an error occurs during mail transmission, "
        "no invoice will be created."
        "If false, invoices will only be created internally.",
    )

    send_dependant_notifications = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Whether to send purchase notifications to users who do"
        " not pay themselves (only valid if invoice mails are "
        "sent at all).",
    )

    send_payment_reminders = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Whether to send payment reminder mails to users with an "
        "account balance below number defined in settings, but "
        "no unbilled purchases (only valid if invoice mails are "
        "sent at all).",
    )

    autolock_accounts = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Automatically lock account if balance is below "
        "{} before and after creating new invoices.".format(
            currency(PybarsysPreferences.Misc.BALANCE_BELOW_AUTOLOCK)
        ),
    )

    comment = forms.CharField(label="Comment", required=False)

    def __init__(self, *args, **kwargs):
        super(InvoicesCreateForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper(form=self)
        self.helper["users"].wrap(layout.Field, size="25")

        self.helper.add_input(layout.Submit("create", "Create"))
        self.helper.add_input(layout.Reset("reset", "Reset"))


class EasyVereinInvoicesCreateForm(forms.Form):
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.active()
        .buyers()
        .pay_themselves()
        .attached_to_easyverein(),
        help_text="Select users to generate EasyVerein invoices for. Only users who "
        "pay themselves and are attached to EasyVerein can be selected.",
    )

    comment = forms.CharField(label="Comment", required=False)

    def __init__(self, *args, **kwargs):
        super(EasyVereinInvoicesCreateForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper(form=self)
        self.helper["users"].wrap(layout.Field, size="25")

        self.helper.add_input(layout.Submit("create", "Create"))
        self.helper.add_input(layout.Reset("reset", "Reset"))


class UserCustomCreationForm(forms.ModelForm):
    """
    Mainly copied from auth.UserCreationForm, b/c UserChangeForm does not allow to change passwords

    If at least one password field is filled in, the passwords are validated. If no password field is filled in,
    the user's password is neither created nor changed.
    """

    purchases_paid_by_other = forms.ModelChoiceField(
        queryset=User.objects.active().pay_themselves(),
        help_text=User._meta.get_field("purchases_paid_by_other").help_text,
        required=False,
    )

    error_messages = {
        "password_mismatch": _("The two password fields didn't match."),
    }
    password1 = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput,
        help_text="If no password is entered, the user password will not be set or changed.",
        required=False,
    )
    password2 = forms.CharField(
        label=_("Password confirmation"),
        widget=forms.PasswordInput,
        strip=False,
        help_text=_("Enter the same password as before, for verification."),
        required=False,
    )

    class Meta:
        model = User
        fields = (
            "email",
            "display_name",
            "password1",
            "password2",
            "purchases_paid_by_other",
            "is_active",
            "is_buyer",
            "is_favorite",
            "is_admin",
            "is_autolocked",
            "easyverein_contact_details_url",
        )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if not PybarsysPreferences.EasyVerein.ACTIVE:
            self.fields.pop("easyverein_contact_details_url", None)

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 or password2:
            if password1 != password2:
                raise forms.ValidationError(
                    self.error_messages["password_mismatch"],
                    code="password_mismatch",
                )
            # Validate only if at least one password was filled in
            auth_forms.password_validation.validate_password(
                self.cleaned_data.get("password2"), self.instance
            )
        return password2

    def save(self, commit=True):
        user = super(UserCustomCreationForm, self).save(commit=False)

        # Only save passwords that were filled in!
        if self.cleaned_data["password1"]:
            user.set_password(self.cleaned_data["password1"])

        if commit:
            user.save()
        return user


class UserCreateForm(UserCustomCreationForm):
    def clean(self):
        cleaned_data = super().clean()
        if PybarsysPreferences.EasyVerein.ACTIVE:
            is_buyer = cleaned_data.get("is_buyer")
            pays_themselves = not cleaned_data.get("purchases_paid_by_other")
            ev_url = cleaned_data.get("easyverein_contact_details_url")
            if is_buyer and pays_themselves and not ev_url:
                raise forms.ValidationError(
                    "Buyers who pay for themselves must be attached to an EasyVerein "
                    "contact. Use 'Fetch contacts from EasyVerein' below to find and "
                    "select a contact."
                )
        return cleaned_data


class UserUpdateForm(UserCustomCreationForm):
    """Update form with one special feature: moving an open balance to a new payer.

    `User.clean()` refuses to turn a self-payer into a dependant while they still owe
    something, so the balance has to go somewhere. It is moved to the new payer, who
    later will get billed for it. This must be confirmed by an admin first, so the
    confirmation field exists only for users who actually carry a balance.
    """

    confirm_balance_transfer = forms.BooleanField(
        label="Yes, move this balance", required=False
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Only offer the confirmation when this particular submit assigns a payer to
        # someone who carries a balance. Opening the page confirms nothing yet, so the
        # field would otherwise appear as a checkbox without any context.
        user = self.instance
        assigns_payer = self.is_bound and self.data.get("purchases_paid_by_other")
        has_balance_to_move = (
            user.pk is not None and user.pays_themselves() and user.open_balance() != 0
        )
        if not assigns_payer or not has_balance_to_move:
            del self.fields["confirm_balance_transfer"]

        if user.pk is not None:
            # Nobody can be their own payer, so do not offer it in the first place.
            payer_field = self.fields["purchases_paid_by_other"]
            payer_field.queryset = payer_field.queryset.exclude(pk=user.pk)

    def becomes_dependant(self) -> bool:
        """True if this edit turns a self-payer into someone else's dependant."""
        if self.instance.pk is None:
            return False
        original = User.objects.get(pk=self.instance.pk)
        return (
            original.pays_themselves()
            and self.cleaned_data.get("purchases_paid_by_other") is not None
        )

    def needs_settlement(self) -> bool:
        """True if the user still has anything open that must not be left behind.

        Deliberately broader than the net amount: a credit of 5 against an unbilled
        purchase of 5 nets out to nothing, yet leaving it alone would bill the purchase
        to the payer while the credit stays stranded on a dependant who can never be
        invoiced again. Settling first guarantees the user is truly empty.
        """
        user = self.instance
        if user.pk is None or not user.pays_themselves():
            return False
        return (
            user.account_balance() != 0
            or Purchase.objects.to_pay_by(user).exists()
            or user.payments().unbilled().exists()
        )

    def clean(self) -> dict:
        cleaned_data = super().clean()
        if not self.becomes_dependant() or not self.needs_settlement():
            return cleaned_data
        payer = cleaned_data["purchases_paid_by_other"]
        if self.instance.dependents().exists() or payer == self.instance:
            # Someone who pays for others cannot become a dependant at all. Let
            # User.clean() say so, instead of first asking to confirm a transfer that is
            # going to be refused anyway. The self-as-payer half is a safety net only:
            # __init__ already keeps the user out of their own payer queryset, so such a
            # value is rejected as an invalid choice long before this runs.
            return cleaned_data

        # From here on this edit is a balance transfer. Tell the model-level check in
        # _post_clean() to stand down - it runs even when this method raises, and its
        # "still owes something" errors describe the very balance being moved, so they
        # would only drown out the more specific messages below. UserUpdateView clears
        # the flag again before saving, so the real check still guards the write.
        self.instance._balance_moves_to_payer = True

        # Same sign convention as everywhere else (negative = owes), so the messages
        # below read correctly for credit too and match the one after the transfer.
        balance = self.instance.open_balance()
        if not balance:
            # Everything the user still has open cancels out, so nothing changes hands.
            # The settlement only marks the open items billed - there is no money for
            # the admin to confirm and nothing the payer has to be able to receive.
            return cleaned_data

        if (
            PybarsysPreferences.EasyVerein.ACTIVE
            and not payer.easyverein_contact_details_url
        ):
            # Moving a known balance onto an account that can never be invoiced would
            # turn a solvable problem into an unsolvable one. Report it on the payer
            # field, which is the one to change - and which the suppressed model-level
            # check would otherwise have been marking.
            # Drop the confirmation too: there is nothing to confirm while the payer
            # cannot receive the balance, and it would render bare, without its
            # explanatory error, because this raise skips the check below.
            self.fields.pop("confirm_balance_transfer", None)
            raise forms.ValidationError(
                {
                    "purchases_paid_by_other": "{} is not attached to an EasyVerein "
                    "contact, so {}'s open balance of {} could never be settled through "
                    "them. Attach {} to EasyVerein first.".format(
                        payer, self.instance, currency(balance), payer
                    )
                }
            )
        if not cleaned_data.get("confirm_balance_transfer"):
            raise forms.ValidationError(
                {
                    "confirm_balance_transfer": "{}'s open balance of {} will move to "
                    "{}. Tick to confirm.".format(
                        self.instance, currency(balance), payer
                    )
                }
            )
        return cleaned_data


class MultiUserChooseForm(forms.Form):
    users = forms.ModelMultipleChoiceField(
        User.objects.active().buyers(), required=True
    )


class SinglePurchaseForm(forms.Form):
    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]

        if quantity < 1:
            raise ValidationError("Invalid quantity")
        else:
            return quantity

    def clean_product_id(self):
        orig_string = self.cleaned_data["product_id"]
        product_id = orig_string

        if product_id.startswith("free_item"):
            # free item purchase
            self.is_free_item_purchase = True
            try:
                # extract product ID
                free_item_id = re.search("^free_item_([0-9]+)$", product_id).group(1)
                free_item_id = int(free_item_id)
            except (AttributeError, ValueError):
                raise ValidationError("ID of free item is not valid")

            try:
                free_item = FreeItem.objects.get(pk=free_item_id)
            except FreeItem.DoesNotExist:
                raise ValidationError("Free item does not exist")

            if not free_item.purchasable:
                raise ValidationError("Free item is not purchasable")

            if not free_item.leftover_quantity > 0:
                raise ValidationError("No free items left")

            return free_item_id
        else:
            # normal product purchase
            self.is_free_item_purchase = False
            try:
                product_id = int(product_id)
            except ValueError:
                raise ValidationError("Product ID is not an integer")

        try:
            Product.objects.active().get(pk=product_id)
            return product_id
        except Product.DoesNotExist:
            raise ValidationError("Invalid product ID")

    quantity = forms.IntegerField()
    product_id = forms.CharField()  # CharField b/c it could be "free_item_N"
    comment = forms.CharField(max_length=50, required=False)
    is_free_item_purchase = False
    purchase_more_for_same_users = forms.BooleanField(required=False)


class SingleUserSinglePurchaseForm(SinglePurchaseForm):
    def clean_user_id(self):
        user_id = self.cleaned_data["user_id"]
        try:
            user = User.objects.active().buyers().get(pk=user_id)

            if user.is_autolocked:
                raise ValidationError(
                    "User is currently autolocked and cannot purchase products"
                )
            elif (
                not user.pays_themselves()
                and user.purchases_paid_by_other.is_autolocked
            ):
                raise ValidationError(
                    "The user responsible for this accounts' payments is currently autolocked"
                )

            return user_id
        except User.DoesNotExist:
            raise ValidationError("Invalid user ID")

    def clean(self):
        super(SingleUserSinglePurchaseForm, self).clean()
        cleaned_data = self.cleaned_data

        if self.is_free_item_purchase and not self.has_error("product_id"):
            # only make additional checks if basic checks have no error

            free_item = FreeItem.objects.get(pk=cleaned_data.get("product_id"))
            if free_item.leftover_quantity < cleaned_data.get("quantity"):
                raise ValidationError(
                    {
                        "quantity": "There are only {} items left, so you cannot purchase {}!".format(
                            free_item.leftover_quantity, cleaned_data.get("quantity")
                        )
                    }
                )
            else:
                pass

            if cleaned_data.get("give_away_free"):
                raise ValidationError(
                    {
                        "give_away_free": "Items that are already free cannot be given away for free."
                    }
                )

    user_id = forms.IntegerField()
    give_away_free = forms.BooleanField(required=False)


class MultiUserSinglePurchaseForm(SinglePurchaseForm):
    comment = forms.CharField(max_length=50, required=False, initial="MultiBuy")
    users_qs = None  # has to be filled in manually

    def clean(self):
        super(MultiUserSinglePurchaseForm, self).clean()
        cleaned_data = self.cleaned_data

        if self.is_free_item_purchase and not self.has_error("product_id"):
            free_item = FreeItem.objects.get(pk=cleaned_data.get("product_id"))
            needed_quantity = cleaned_data.get("quantity") * self.users_qs.count()
            if free_item.leftover_quantity < needed_quantity:
                raise ValidationError(
                    {
                        "quantity": "There are only {} items left, so you cannot purchase {}!".format(
                            free_item.leftover_quantity, needed_quantity
                        )
                    }
                )
            else:
                pass


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        exclude = ("",)


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        exclude = ("",)


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        exclude = ("invoice", "is_virtual_payment")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = User.objects.filter(
            purchases_paid_by_other__isnull=True
        )


class UserSettleBalanceForm(forms.Form):
    """Write off a balance inside pybarsys only, without sending a bill.

    This is the escape hatch for accounts that can no longer be settled the normal way:
    a member who died, someone who moved away and cannot be reached, or a user who is
    not (and cannot be) attached to EasyVerein and therefore cannot be invoiced at all.
    It is a last resort and leaves the books uneven, so a reason is mandatory.
    """

    reason = forms.CharField(
        label="Reason",
        required=True,
        max_length=500,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "e.g. User has died; balance written off per board decision",
            }
        ),
        help_text="Why can this balance not be settled the normal way? Stored in full "
        "on the invoice; the payment keeps a shortened copy, so put the gist first.",
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.helper = FormHelper(form=self)
        self.helper.add_input(
            layout.Submit("settle", "Invoice and settle to 0", css_class="btn-warning")
        )


class FreeItemForm(forms.ModelForm):
    class Meta:
        model = FreeItem
        exclude = ("",)

    def __init__(self, *args, **kwargs):
        super(FreeItemForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper(form=self)
        self.helper.add_input(layout.Submit("save", "Save"))


class StatsDisplayForm(forms.ModelForm):
    class Meta:
        model = StatsDisplay
        exclude = ("",)


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = [
            "easyverein_api_token",
            "easyverein_bank_account_id",
            "easyverein_finalize_invoices",
        ]
        labels = {
            "easyverein_api_token": "API token",
            "easyverein_bank_account_id": "Bank account ID",
            "easyverein_finalize_invoices": "Finalize invoices",
        }
        # Do not echo the stored token back into the page. It renders empty; an empty
        # submit keeps the current token (see clean_easyverein_api_token).
        widgets = {
            "easyverein_api_token": forms.PasswordInput(render_value=False),
        }
        help_texts = {
            "easyverein_api_token": "Leave blank to keep the current token.",
        }

    def clean_easyverein_api_token(self):
        # The token field renders empty (PasswordInput), so a blank submit means
        # "unchanged" rather than "clear the token".
        value = self.cleaned_data.get("easyverein_api_token")
        return value or self.instance.easyverein_api_token

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The EasyVerein fields are only shown/editable when the integration is active
        # (mirrors the template). Removing them when inactive avoids spurious validation
        # errors and prevents a submit from overwriting stored values with blanks.
        if not PybarsysPreferences.EasyVerein.ACTIVE:
            for field_name in (
                "easyverein_api_token",
                "easyverein_bank_account_id",
                "easyverein_finalize_invoices",
            ):
                self.fields.pop(field_name, None)
