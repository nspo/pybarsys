import datetime
from collections import defaultdict
from decimal import Decimal

from django.contrib.auth.models import (
    BaseUserManager, AbstractBaseUser
)
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import IntegrityError
from django.db import models
from django.db.models import DecimalField
from django.db.models import F
from django.urls import reverse
from django.utils import formats
from django.utils import timezone
from django.utils.timezone import localtime

from barsys.templatetags.barsys_helpers import currency


class DefaultSelectOrPrefetchManager(models.Manager):
    # https://stackoverflow.com/a/21291161/997151
    def __init__(self, *args, **kwargs):
        self._select_related = kwargs.pop('select_related', None)
        self._prefetch_related = kwargs.pop('prefetch_related', None)

        super(DefaultSelectOrPrefetchManager, self).__init__(*args, **kwargs)

    def get_queryset(self, *args, **kwargs):
        qs = super(DefaultSelectOrPrefetchManager, self).get_queryset(*args, **kwargs)

        if self._select_related:
            qs = qs.select_related(*self._select_related)
        if self._prefetch_related:
            qs = qs.prefetch_related(*self._prefetch_related)

        return qs


class UserQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def buyers(self):
        return self.filter(is_buyer=True)

    def favorites(self):
        return self.filter(is_favorite=True)

    def pay_themselves(self):
        return self.filter(purchases_paid_by_other=None)

    def purchases(self):
        return Purchase.objects.filter(user__in=self)


class UserManager(BaseUserManager):
    def get_queryset(self):
        return UserQuerySet(self.model, using=self._db)

    def create_user(self, email, display_name, password=None):
        if not email:
            raise ValueError('Users must have an email address')

        user = self.model(
            email=self.normalize_email(email),
        )

        user.display_name = display_name
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, display_name, password):
        user = self.create_user(
            email,
            display_name,
            password=password,
        )
        user.is_admin = True
        user.save(using=self._db)
        return user

    def get_by_natural_key(self, username):
        """ Match username/email case-insensitive """
        return self.get(**{self.model.USERNAME_FIELD + '__iexact': username})


from django.db.models import Q


class User(AbstractBaseUser):
    email = models.EmailField(max_length=255, unique=True, blank=False, help_text="Email is used as username when "
                                                                                  "logging into the user-only area")

    display_name = models.CharField(max_length=40, unique=True, blank=False, help_text="What is shown on the "
                                                                                       "main purchase page")

    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False, help_text="User may login as admin")
    is_buyer = models.BooleanField(default=True, help_text="User may buy products")
    is_favorite = models.BooleanField(default=False, help_text="User is shown under favorites")
    is_autolocked = models.BooleanField(default=False, help_text="User was automatically locked "
                                                                 "due to the outstanding balance")

    purchases_paid_by_other = models.ForeignKey("self", on_delete=models.PROTECT, default=None, null=True, blank=True,
                                                help_text="If set, another active user (who pays for their own "
                                                          "purchases) is responsible to pay for all purchases made by "
                                                          "this user. Invoices are sent to the responsible user, and a "
                                                          "copy goes to the dependent as notification.",
                                                limit_choices_to=(Q(purchases_paid_by_other=None)))

    # Dates
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    objects = UserManager.from_queryset(UserQuerySet)()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def clean(self):
        if self.purchases_paid_by_other == self:
            raise ValidationError({'purchases_paid_by_other': "This field cannot be set to the same user"})
        if self.purchases_paid_by_other_id is not None:
            if self.purchases_paid_by_other.purchases_paid_by_other_id is not None:
                raise ValidationError({'purchases_paid_by_other': "Purchases cannot be paid by someone who does not "
                                                                  "pay for their own purchases."})
            dependents = self.dependents()
            if dependents.exists():
                other_names = [u.display_name for u in dependents]
                raise ValidationError({'purchases_paid_by_other': "This user pays for the following users, so "
                                                                  "their purchases cannot be paid by someone else: {}"
                                      .format(', '.join(other_names))})
        if self.pk is not None:
            # Check whether this user should pay for other active users' purchases but is not active
            dependents = self.dependents().active()
            if not self.is_active and dependents.exists():
                raise ValidationError({'is_active': "This user has to pay for purchases of the following active users"
                                                    ", so they cannot be deactivated: {}".
                                      format(", ".join([d.display_name for d in dependents]))})

            orig = User.objects.get(pk=self.pk)
            if orig.purchases_paid_by_other_id is None and self.purchases_paid_by_other_id is not None:
                # change from self-paying to dependant
                if self.account_balance() < 0:
                    raise ValidationError({'purchases_paid_by_other':
                                               "Cannot make user a dependant if they have a negative account balance."})
                if self.payments().unbilled().exists():
                    raise ValidationError({'purchases_paid_by_other':
                                               "Cannot make user a dependant if they have unbilled payments"})

    def save(self, *args, **kwargs):
        self.clean()  # do not call full_clean b/c password may be empty
        super(User, self).save(*args, **kwargs)

    def get_full_name(self):
        # The user is identified by their email address
        return self.email

    def get_short_name(self):
        # The user is identified by their email address
        return self.email

    def __str__(self):
        # __unicode__ on Python 2
        return "{} ({})".format(self.display_name, self.email)

    def has_perm(self, perm, obj=None):
        "Does the user have a specific permission?"
        # Simplest possible answer: Yes, always
        return True

    def has_module_perms(self, app_label):
        "Does the user have permissions to view the app `app_label`?"
        # Simplest possible answer: Yes, always
        return True

    @property
    def is_staff(self):
        "Is the user a member of staff?"
        # Simplest possible answer: All admins are staff
        return self.is_admin

    @property
    def is_superuser(self):
        return self.is_admin

    def num_purchases(self):
        return Purchase.objects.filter(user_id=self.pk).count()

    class Meta:
        ordering = ["display_name"]

    def get_absolute_url(self):
        return reverse('admin_user_detail', kwargs={'pk': self.pk})

    def cannot_be_deleted(self):
        if self.purchases().count() == 0:
            return False
        else:
            return "This user cannot be deleted because they have purchases."

    def purchases(self):
        return Purchase.objects.filter(user=self)

    def invoices(self):
        return Invoice.objects.filter(recipient=self)

    def payments(self):
        return Payment.objects.filter(user=self)

    def dependents(self):
        """ FIXME: name """
        return User.objects.filter(purchases_paid_by_other=self)

    def pays_themselves(self):
        return self.purchases_paid_by_other_id is None

    def account_balance(self):
        # rounding should NOT be necessary (and really is not), but there is
        #   a problem with SQLite not handling Decimal objects quite as it
        #   should: https://code.djangoproject.com/ticket/29823
        #   This currently is mainly used so that a pybarsys unit test
        #   does not fail, which is... somewhat suboptimal
        return -round(self.invoices().sum_amount(), 2)


class Category(models.Model):
    name = models.CharField(max_length=40, unique=True, blank=False)

    def __str__(self):
        return "{}".format(self.name)

    def get_number_products(self):
        return self.get_products().count()

    get_number_products.short_description = "Number of products"

    def get_products(self):
        return Product.objects.filter(category_id=self.pk)

    class Meta:
        verbose_name_plural = "Categories"

    def get_absolute_url(self):
        return reverse('admin_category_detail', kwargs={'pk': self.pk})

    def cannot_be_deleted(self):
        product_count = Product.objects.filter(category=self).count()
        if product_count > 0:
            return "There is at least one product in this category"
        else:
            return False

    class Meta:
        ordering = ["name"]


class ProductQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class Product(models.Model):
    """ name of product is not unique, because there can be other products with the same name but different amount"""
    name = models.CharField(max_length=40, blank=False, help_text="Multiple products can have the same name "
                                                                  "as long as the amount is different")
    price = models.DecimalField(max_digits=5, decimal_places=2, blank=False, null=False,
                                validators=[MinValueValidator(Decimal('0.01'))])
    amount = models.CharField(max_length=12, blank=False)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, null=False)

    is_active = models.BooleanField(default=True, help_text="Whether this product is shown on the purchasing page")
    is_bold = models.BooleanField(default=False, help_text="Whether this product is shown bold on the purchasing page")

    objects = ProductQuerySet.as_manager()

    def __str__(self):
        return "{} ({}, {})".format(self.name, self.amount, currency(self.price))

    class Meta:
        unique_together = ["name", "amount"]
        ordering = ["category__name", "-is_bold", "name", ]

    def cannot_be_deleted(self):
        return False

    def get_absolute_url(self):
        return reverse('admin_product_detail', kwargs={'pk': self.pk})


class InvoiceQuerySet(models.QuerySet):
    def sum_amount(self):
        total_amount = self.aggregate(total_amount=models.Sum(F("amount_purchases") - F("amount_payments"))).get(
            "total_amount")
        if total_amount is not None:
            return total_amount
        else:
            return Decimal('0')


class InvoiceManager(models.Manager):
    def create_for_user(self, user, comment = ""):
        if not user.pays_themselves():
            raise IntegrityError("Cannot create an invoice for someone who does not pay for themselves")

        invoice = Invoice()
        invoice.recipient = user

        invoice.amount_purchases = 0
        invoice.amount_payments = 0
        invoice.save()  # Save so that an ID is created

        own_purchases = user.purchases().unbilled()

        invoice.amount_purchases += own_purchases.sum_cost()
        # Call update only after summing up the costs, b/c otherwise they are not unbilled anymore
        own_purchases.update(invoice=invoice)
        # print("Subtotal for own purchases: {}".format(subtotal))

        other_purchases = Purchase.objects.to_pay_by(user).order_by('user')

        invoice.amount_purchases += other_purchases.sum_cost()
        other_purchases.update(invoice=invoice)

        # Check non-invoiced payments
        own_payments = user.payments().unbilled()
        invoice.amount_payments += own_payments.sum_amount()

        own_payments.update(invoice=invoice)

        invoice.comment = comment;

        invoice.save()

        return invoice


class Invoice(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.PROTECT)
    amount_purchases = models.DecimalField(max_digits=7, decimal_places=2, blank=False, null=False,
                                           validators=[MinValueValidator(Decimal('0.00'))])

    amount_payments = models.DecimalField(max_digits=7, decimal_places=2, blank=False, null=False)

    # Dates
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    comment = models.TextField(default="")

    objects = InvoiceManager.from_queryset(InvoiceQuerySet)()

    class Meta:
        ordering = ["-created_date"]

    def purchases(self):
        return Purchase.objects.filter(invoice=self)

    def payments(self):
        return Payment.objects.filter(invoice=self)

    def due(self):
        return self.amount_purchases - self.amount_payments

    def __str__(self):
        return "Invoice to {} over {} on {}".format(self.recipient,
                                                    currency(self.amount_purchases - self.amount_payments),
                                                    formats.date_format(localtime(self.created_date),
                                                                        "SHORT_DATETIME_FORMAT"))

    def cannot_be_deleted(self):
        return False

    def own_purchases(self):
        return self.purchases().paid_as_self(self.recipient)

    def other_purchases(self):
        return self.purchases().paid_as_other(self.recipient)

    def has_dependant_purchases(self):
        if self.own_purchases().count() == self.purchases().count():
            return False
        else:
            return True

    def other_purchases_grouped(self):
        """ Create a list of tuples in the format (User, PurchaseQuerySet) of purchases
            that the recipient paid for other users
        """
        other_purchases = self.other_purchases()

        other_users = other_purchases.values("user").order_by("user").distinct()

        other_purchases_grouped = []

        for u in other_users:
            user_id = u["user"]
            other_purchases_grouped.append(
                (User.objects.get(pk=user_id), other_purchases.filter(user=user_id).order_by("-created_date")))

        return other_purchases_grouped

    def get_absolute_url(self):
        return reverse('admin_invoice_detail', kwargs={'pk': self.pk})


class PurchaseQuerySet(models.QuerySet):
    def unbilled(self):
        return self.filter(invoice=None)

    def to_pay_by(self, user):
        """ Unbilled purchases that a user must pay for (either b/c they bought something themselves
            or have to pay for others)
        """
        return self.unbilled().filter(Q(user__purchases_paid_by_other=user) |
                                      Q(user=user, user__purchases_paid_by_other__isnull=True))

    def paid_as_other(self, payer):
        """ Invoiced purchases that were paid by a user for others """
        return self.filter(Q(invoice__recipient=payer) & ~Q(user=payer))

    def paid_as_self(self, payer):
        """ Invoiced purchases that were paid by a user for themselves """
        return self.filter(Q(invoice__recipient=payer) & Q(user=payer))

    def sum_cost(self):
        total_cost = self.aggregate(total_cost=models.Sum(F("quantity") * F("product_price"),
                                                          output_field=DecimalField(decimal_places=2))).get(
            "total_cost")
        if total_cost is not None:
            return total_cost
        else:
            return Decimal('0')

    def sum_quantity(self):
        total_quantity = self.aggregate(total_quantity=models.Sum(F("quantity"))).get("total_quantity")
        if total_quantity is not None:
            return total_quantity
        else:
            return 0

    def stats_purchases_by_category_and_product(self):
        """ Calculate sum of purchases of each product and group by category and product
            Limit parameter would not make a lot of sense here
        """

        # Purchase quantity as list of dicts
        purchases_per_product = self.values("product_category", "product_name", "product_amount") \
            .annotate(total_quantity=models.Sum("quantity")).order_by("-total_quantity").distinct()

        # Create dict (categories) of list (products)
        categories = defaultdict(list)
        for prod in purchases_per_product:
            categories[prod["product_category"]].append(prod)

        # Create list (categories) of tuples in the format
        # [(category, [{'product_name': 10, 'total_quantity': 5, ...}, {...}]), ...]
        return sorted(categories.items())  # Sort by category name

    def stats_purchases_by_user(self, limit=5):
        """ Like stats_purchases_by_category_and_product, but groups by user """

        # Purchase quantity as list of dicts
        purchases_per_user = self.values("user", "user__display_name") \
                                 .annotate(total_quantity=models.Sum("quantity")).order_by(
            "-total_quantity").distinct()[:limit]

        # Create list of tuples in the format (user, total_quantity)
        users = []
        for p in purchases_per_user:
            users.append((p["user"], p["user__display_name"], p["total_quantity"]))

        return users

    def stats_cost_by_user(self, limit=5):
        """ Calculate total cost of purchases and group by user """
        cost_per_user = self.values("user", "user__display_name"). \
                            annotate(total_cost=models.Sum(F("quantity") * F("product_price"),
                                                           output_field=DecimalField(decimal_places=2))). \
                            filter(total_cost__gt=0).order_by("-total_cost")[:limit]

        # Create list of tuples [(user, total_cost), ...]
        users = []
        for u in cost_per_user:
            users.append((u["user"], u["user__display_name"], u["total_cost"]))

        return users


class PurchaseManager(models.Manager):
    def create_from_product(self, product, **kwargs):
        p = Purchase(product_amount=product.amount, product_category=product.category.name, product_name=product.name,
                     product_price=product.price, **kwargs)
        p.save()
        return p


class Purchase(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT, null=False)
    # Don't save product reference as foreign key, b/c it could be changed after purchase
    product_category = models.CharField(max_length=40, blank=False)
    product_name = models.CharField(max_length=40, blank=False)
    product_price = models.DecimalField(max_digits=5, decimal_places=2, blank=False, null=False,
                                        validators=[MinValueValidator(Decimal('0.00'))])
    product_amount = models.CharField(max_length=12, blank=False)
    quantity = models.PositiveIntegerField(default=1, null=False, blank=False)

    comment = models.CharField(max_length=50, blank=True, help_text="An optional comment for this purchase")

    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, blank=True, null=True)

    is_free_item_purchase = models.BooleanField(default=False, help_text="Whether this purchase was done with a free "
                                                                         "item (i.e. it was shown as free on the main page)")

    free_item_description = models.CharField(max_length=120, blank=True,
                                             help_text="Description of free item (only if this was purchased for free)")

    # Dates
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    objects = PurchaseManager.from_queryset(PurchaseQuerySet)()

    class Meta:
        ordering = ["-created_date"]

    def __str__(self):
        return "{}x {} ({}, {})".format(self.quantity, self.product_name, self.user.display_name, currency(self.cost()))

    def cost(self):
        return self.quantity * self.product_price

    def get_absolute_url(self):
        return reverse('admin_purchase_detail', kwargs={'pk': self.pk})

    def cannot_be_deleted(self):
        """ Returns False or an explanation why this cannot be deleted """
        if self.has_invoice():
            return "This purchase already has an invoice"
        else:
            return False

    def has_invoice(self):
        return self.invoice_id is not None

    def clean(self, *args, **kw):
        if self.pk is not None:
            orig = Purchase.objects.get(pk=self.pk)
            if orig.has_invoice():
                field_names = [field.name for field in Purchase._meta.fields]
                for field_name in field_names:
                    if getattr(orig, field_name) != getattr(self, field_name):
                        # some attribute has changed, although there was already an invoice
                        raise ValidationError("Invoiced purchases may not be changed")
        super(Purchase, self).clean(*args, **kw)

    def save(self, *args, **kw):
        self.full_clean()
        super(Purchase, self).save(*args, **kw)


class PaymentQuerySet(models.QuerySet):
    def sum_amount(self):
        """ Total amount of all payments """
        total_amount = self.aggregate(total_amount=models.Sum(F("amount"))).get("total_amount")
        if total_amount is not None:
            return total_amount
        else:
            return Decimal('0')

    def unbilled(self):
        return self.filter(invoice=None)


class Payment(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=6, decimal_places=2, blank=False, null=False,
                                 help_text="Positive amounts are deposits by the user. "
                                           "Negative amounts are payouts to the user.")
    comment = models.CharField(max_length=100, blank=True)

    PAYMENT_METHOD_CASH = "CASH"
    PAYMENT_METHOD_BANK = "BANK"
    PAYMENT_METHOD_OTHER = "OTHR"
    PAYMENT_METHOD_CHOICES = ((PAYMENT_METHOD_CASH, "Cash"),
                              (PAYMENT_METHOD_BANK, "Bank transfer"),
                              (PAYMENT_METHOD_OTHER, "Other"))
    payment_method = models.CharField(max_length=4, choices=PAYMENT_METHOD_CHOICES, default=PAYMENT_METHOD_BANK)

    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, blank=True, null=True)

    # Dates
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    value_date = models.DateField(default=datetime.date.today, help_text="Date when payment is considered effective "
                                                                         "(only for display)")

    objects = PaymentQuerySet.as_manager()

    def get_absolute_url(self):
        return reverse('admin_payment_detail', kwargs={'pk': self.pk})

    class Meta:
        ordering = ["-created_date"]

    def __str__(self):
        return "Payment of {} by {}".format(currency(self.amount), self.user.display_name)

    def has_invoice(self):
        return self.invoice_id is not None

    def cannot_be_deleted(self):
        """ Returns False or an explanation why this payment cannot be deleted """
        if self.has_invoice():
            return "This payment already has an invoice"
        else:
            return False

    def save(self, *args, **kw):
        if not self.user.pays_themselves():
            raise IntegrityError(
                "Users who do not pay themselves may not have new or changed payments. Make user independent first to do that.")

        """ Check whether obj has invoice but was changed """
        if self.pk is not None:
            orig = Payment.objects.get(pk=self.pk)
            if orig.has_invoice():
                field_names = [field.name for field in Payment._meta.fields]
                for field_name in field_names:
                    if getattr(orig, field_name) != getattr(self, field_name):
                        # some attribute has changed, although there was already an invoice
                        raise IntegrityError("Invoiced payments may not be changed")
        super(Payment, self).save(*args, **kw)


class StatsDisplay(models.Model):
    """ Admin-defined filters that can be shown as stats in frontend """
    title = models.CharField(max_length=30, blank=False, unique=True)
    row_string = models.CharField(max_length=15, blank=True,
                                  help_text="This is shown on the right side of each stats row in the format "
                                            "'[row_string] [user_name]', so one example row could be "
                                            "'10x Coffee by Peter' with 'Coffee by' being the row_string")

    filter_by_category = models.ManyToManyField(Category, blank=True, help_text="If none, all categories are used")
    filter_by_product = models.ManyToManyField(Product, blank=True, help_text="If none, all products are used")

    FIXED_DURATION = "FIXED"
    SINCE_MONDAY = "MONDAY"
    SINCE_1ST = "1st"
    SINCE_JAN_1ST = "JAN_1st"
    SINCE_TODAY_MIDNIGHT = "TOD_MID"
    SINCE_4pm = "4pm"

    TIME_PERIOD_METHOD_CHOICES = ((FIXED_DURATION, "Fixed duration"),
                                  (SINCE_MONDAY, "Since Monday of current week (midnight)"),
                                  (SINCE_1ST, "Since 1st of current month (midnight)"),
                                  (SINCE_JAN_1ST, "Since January 1st of current year (midnight)"),
                                  (SINCE_TODAY_MIDNIGHT, "Since midnight (00:00) of current day"),
                                  (SINCE_4pm, "Since last time it was 4pm (16:00)"))

    time_period_method = models.CharField(max_length=7, choices=TIME_PERIOD_METHOD_CHOICES, default=SINCE_MONDAY,
                                          help_text="Method of how to determine the time frame in which purchases "
                                                    "count into this statistics display.")

    time_period = models.DurationField(default=datetime.timedelta(weeks=1),
                                       help_text="Duration over which statistics are to be evaluated in the format "
                                                 "'DAYS HOURS:MINUTES:SECONDS'. Only used if time period method "
                                                 "is 'fixed duration'")

    SORT_BY_NUM_PURCHASES = "NP"
    SORT_BY_TOTAL_COST_SHOW_RANK = "TC"
    SORT_BY_AND_SHOW_CHOICES = ((SORT_BY_NUM_PURCHASES, "Sort by and show number of purchases"),
                                (SORT_BY_TOTAL_COST_SHOW_RANK, "Sort by total cost and show rank"))
    sort_by_and_show = models.CharField(max_length=2, choices=SORT_BY_AND_SHOW_CHOICES, default=SORT_BY_NUM_PURCHASES)

    # A special boolean field that may only be True for one StatsDisplay
    # i.e. only one StatsDisplay can be the chosen one
    # Need to override save() for this
    show_by_default = models.BooleanField(default=False,
                                          help_text="Whether this should always be shown first. " \
                                                    "If not, it can be selected by cycling through the other ones, " \
                                                    "as long as any one is shown by default.")

    class Meta:
        ordering = ["-show_by_default", "title"]

    def save(self, *args, **kwargs):
        """Make sure that only one StatsDisplay is shown by default"""
        if self.show_by_default:
            queryset = StatsDisplay.objects.filter(show_by_default=True)
            if self.pk:
                # already exists
                queryset = queryset.exclude(pk=self.pk)
            if queryset.exists():
                queryset.update(show_by_default=False)
        super(StatsDisplay, self).save(*args, **kwargs)

    def __str__(self):
        return self.title

    def example_row(self):
        if self.sort_by_and_show == self.SORT_BY_NUM_PURCHASES:
            return "5x {} Peter".format(self.row_string)
        elif self.sort_by_and_show == self.SORT_BY_TOTAL_COST_SHOW_RANK:
            return "1. {} Peter".format(self.row_string)
        else:
            return "not supported"

    def get_absolute_url(self):
        return reverse('admin_statsdisplay_detail', kwargs={'pk': self.pk})

    def cannot_be_deleted(self):
        return False

    def time_period_begin(self):
        if self.time_period_method == self.FIXED_DURATION:
            return localtime(timezone.now()) - self.time_period
        elif self.time_period_method == self.SINCE_MONDAY:
            now = localtime(timezone.now())
            last_monday = now - datetime.timedelta(days=now.weekday())
            last_monday = last_monday.replace(hour=0, minute=0, second=0, microsecond=0)  # midnight
            return last_monday
        elif self.time_period_method == self.SINCE_1ST:
            now = localtime(timezone.now())
            month_1st = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return month_1st
        elif self.time_period_method == self.SINCE_JAN_1ST:
            now = localtime(timezone.now())
            jan_1st = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            return jan_1st
        elif self.time_period_method == self.SINCE_TODAY_MIDNIGHT:
            now = localtime(timezone.now())
            midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return midnight
        elif self.time_period_method == self.SINCE_4pm:
            now = localtime(timezone.now())
            if now.hour >= 16:
                # kein Bier vor vier
                last4pm = now.replace(hour=16, minute=0, second=0, microsecond=0)
            else:
                yesterday = now - datetime.timedelta(days=1)
                last4pm = yesterday.replace(hour=16, minute=0, second=0, microsecond=0)

            return last4pm


class ProductAutochange(models.Model):
    """ Set of changes that can be applied to one product """
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    pc_set = models.ForeignKey("ProductAutochangeSet", on_delete=models.CASCADE)

    set_price = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                    validators=[MinValueValidator(Decimal('0'))],
                                    help_text="If set, will change the price to this value")

    NO_CHANGE = "NC"
    CHANGE_TO_YES = "YES"
    CHANGE_TO_NO = "NO"

    BOOLEAN_CHANGE_CHOICES = ((NO_CHANGE, "No change"),
                              (CHANGE_TO_YES, "Change to yes"),
                              (CHANGE_TO_NO, "Change to no"),)

    change_active = models.CharField(max_length=3,
                                     choices=BOOLEAN_CHANGE_CHOICES,
                                     default=NO_CHANGE)

    change_bold = models.CharField(max_length=3,
                                   choices=BOOLEAN_CHANGE_CHOICES,
                                   default=NO_CHANGE)

    def execute(self):
        """ Execute product change """
        product = self.product
        initial_data = product.__dict__.copy()

        if self.set_price is not None:
            product.price = self.set_price

        if self.change_active == self.CHANGE_TO_YES:
            product.is_active = True
        elif self.change_active == self.CHANGE_TO_NO:
            product.is_active = False

        if self.change_bold == self.CHANGE_TO_YES:
            product.is_bold = True
        elif self.change_bold == self.CHANGE_TO_NO:
            product.is_bold = False

        if product.price != initial_data["price"] or product.is_active != initial_data["is_active"] or \
                product.is_bold != initial_data["is_bold"]:
            # only save if changed
            product.save()


class ProductAutochangeSet(models.Model):
    """ Set of product autochanges that can each be applied to a product """
    title = models.CharField(max_length=30, blank=False, unique=True)
    description = models.CharField(max_length=255, blank=True)
    products = models.ManyToManyField(Product, through=ProductAutochange, help_text="These products will be changed.")

    change_others_active = models.CharField(max_length=3,
                                            choices=ProductAutochange.BOOLEAN_CHANGE_CHOICES,
                                            default=ProductAutochange.NO_CHANGE,
                                            help_text="Change active state of other products")

    change_others_bold = models.CharField(max_length=3,
                                          choices=ProductAutochange.BOOLEAN_CHANGE_CHOICES,
                                          default=ProductAutochange.NO_CHANGE,
                                          help_text="Change bold state of other products")

    objects = DefaultSelectOrPrefetchManager(prefetch_related=("products",))

    def get_absolute_url(self):
        return reverse("admin_productautochangeset_list")

    def cannot_be_deleted(self):
        return False

    def __str__(self):
        return "{} ({} product(s) specified)".format(self.title, self.products.count())

    def execute(self):
        unspecified_products = Product.objects.exclude(pk__in=self.products.all())
        for product in unspecified_products:
            initial_data = product.__dict__.copy()

            if self.change_others_active == ProductAutochange.CHANGE_TO_YES:
                product.is_active = True
            elif self.change_others_active == ProductAutochange.CHANGE_TO_NO:
                product.is_active = False

            if self.change_others_bold == ProductAutochange.CHANGE_TO_YES:
                product.is_bold = True
            elif self.change_others_bold == ProductAutochange.CHANGE_TO_NO:
                product.is_bold = False

            if product.price != initial_data["price"] or product.is_active != initial_data["is_active"] or \
                    product.is_bold != initial_data["is_bold"]:
                # only save if changed
                product.save()

        for pac in self.productautochange_set.all().select_related("product"):
            pac.execute()

    class Meta:
        ordering = ["title"]

    def import_current_state(self):
        if not self.pk:
            raise IntegrityError("Only saved PACS may be used to import the current state")

        self.productautochange_set.all().delete()

        self.change_others_active = ProductAutochange.CHANGE_TO_NO
        self.change_others_bold = ProductAutochange.NO_CHANGE
        self.save()

        new_pacs = []
        for product in Product.objects.active():
            pac = ProductAutochange(product=product, pc_set=self)

            pac.set_price = product.price
            pac.change_active = ProductAutochange.CHANGE_TO_YES
            if product.is_bold:
                pac.change_bold = ProductAutochange.CHANGE_TO_YES
            else:
                pac.change_bold = ProductAutochange.CHANGE_TO_NO

            new_pacs.append(pac)

        ProductAutochange.objects.bulk_create(new_pacs)


class FreeItem(models.Model):
    """ Model to describe products which are free, but only for a limited number of purchases """
    giver = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                              help_text="User thanks to whom this product is free")

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    leftover_quantity = models.PositiveIntegerField(null=False, blank=False,
                                                    help_text="How many items can still be purchased for free")

    comment = models.CharField(max_length=50, blank=True)

    purchasable = models.BooleanField(default=True,
                                      help_text="Whether these free items are shown on the main purchase page. "
                                                "If no, only admins can change the leftover quantity.")

    # Dates
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Free {} ({} item(s) leftover)".format(self.product.name, self.leftover_quantity)

    def verbose_str(self):
        desc = "Free {} (".format(self.product.name)
        if self.giver:
            desc += "giver: {}, ".format(self.giver.display_name)
        if self.comment:
            desc += "comment: {}, ".format(self.comment)
        desc += "{} item(s) leftover)".format(self.leftover_quantity)

        return desc

    def save(self, *args, **kw):
        """ Extra check whether leftover_quantity >= 0 """
        if self.leftover_quantity < 0:
            raise IntegrityError("There may not be a leftover quantity smaller than zero")
        super(FreeItem, self).save(*args, **kw)

    def cannot_be_deleted(self):
        return False

    class Meta:
        ordering = ["-leftover_quantity"]

    def get_absolute_url(self):
        return reverse('admin_freeitem_list')
