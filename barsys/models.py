from django.db import models
from django.contrib.auth.models import (
    BaseUserManager, AbstractBaseUser
)
from collections import defaultdict
from django.db.models import F
import datetime
from django.utils import timezone
from django.db.models import DecimalField
from django.utils.translation import ugettext_lazy as _
import decimal


class UserManager(BaseUserManager):
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

    # Active buyers
    def filter_buyers(self):
        return self.filter(is_active=True, is_buyer=True)

    # Active favorite buyers
    def filter_favorites(self):
        return self.filter_buyers().filter(is_favorite=True)


class User(AbstractBaseUser):
    email = models.EmailField(max_length=255, unique=True, blank=False)

    display_name = models.CharField(max_length=40, unique=True, blank=False)


    is_active = models.BooleanField(default=True, help_text="User account is activated")
    is_admin = models.BooleanField(default=False, help_text="User may login as admin")
    is_buyer = models.BooleanField(default=True, help_text="User may buy products")
    is_favorite = models.BooleanField(default=False, help_text="User is shown under favorites")

    purchases_paid_by = models.ForeignKey("self", on_delete=models.PROTECT, default=None, null=True, blank=True,
                                          help_text="Someone else is responsible to pay for all purchases made "
                                                    "by this user. Invoices are sent to the responsible person and a "
                                                    "copy is sent to the user itself as a notification.")

    # Dates
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

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


class Category(models.Model):
    name = models.CharField(max_length=30, unique=True, blank=False)

    def __str__(self):
        return "{}".format(self.name)

    def get_number_products(self):
        return self.get_products().count()

    get_number_products.short_description = "Number of products"

    def get_products(self):
        return Product.objects.filter(category__pk=self.pk)

    class Meta:
        verbose_name_plural = "Categories"


class Product(models.Model):
    """ name of Product is not unique, because there can be other products with the same name but different amount"""
    name = models.CharField(max_length=40, blank=False, help_text="Multiple products can have the same name "
                            "as long as the amount is different")
    price = models.DecimalField(max_digits=5, decimal_places=2, blank=False, null=False)
    amount = models.CharField(max_length=10, blank=False)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, null=False)

    def __str__(self):
        return "{} ({}, {})".format(self.name, self.amount, self.price)

    class Meta:
        unique_together = ["name", "amount"]
        ordering = ["category__name", "name", "amount"]


class Invoice(models.Model):
    # Dates
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)


class PurchaseManager(models.Manager):
    def purchases_by_category_and_product(self, *args, **kwargs):
        """ Calculate sum of purchases of each product and group by category and product
            All necessary filters (e.g. user=this_user) need to be passed as arguments
        """

        # Purchase quantity as list of dicts
        purchases_per_product = self.filter(*args, **kwargs).values("product_category", "product_name",
                                                                    "product_amount") \
            .annotate(total_quantity=models.Sum("quantity")).order_by("-total_quantity").distinct()

        # Create dict (categories) of list (products)
        categories = defaultdict(list)
        for prod in purchases_per_product:
            categories[prod["product_category"]].append(prod)

        # Create list (categories) of tuples in the format
        # [(category, [{'product_name': 10, 'total_quantity': 5, ...}, {...}]), ...]
        return sorted(categories.items())

    def purchases_by_user(self, *args, **kwargs):
        """ Like purchases_by_category_and_product, but groups by user """

        # Purchase quantity as list of dicts
        purchases_per_user = self.filter(*args, **kwargs).values("user") \
            .annotate(total_quantity=models.Sum("quantity")).order_by("-total_quantity").distinct()

        # Create list of tuples in the format (user, total_quantity)
        users = []
        for p in purchases_per_user:
            users.append((User.objects.get(pk=p["user"]), p["total_quantity"]))

        return users

    def cost_by_user(self, *args, **kwargs):
        """ Calculate total cost of purchases and group by user """
        cost_per_user = User.objects.filter(*args, **kwargs).\
            annotate(total_cost=models.Sum(F("purchase__quantity") * F("purchase__product_price"), output_field=DecimalField(decimal_places=2))).\
            filter(total_cost__gt=0).order_by("-total_cost")

        # Create list of tuples [(user, total_cost), ...]
        users = []
        for u in cost_per_user:
            users.append((u, u.total_cost))

        return users


class Purchase(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT, null=False)
    # Don't save product reference as foreign key, b/c it could be changed after purchase
    product_category = models.CharField(max_length=30, blank=False)
    product_name = models.CharField(max_length=40, blank=False)
    product_price = models.DecimalField(max_digits=5, decimal_places=2, blank=False, null=False)
    product_amount = models.CharField(max_length=10, blank=False)
    quantity = models.PositiveIntegerField(default=1, null=False, blank=False)

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, blank=True, null=True)

    # Dates
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    objects = PurchaseManager()

    def __str__(self):
        return "{}x {} ({})".format(self.quantity, self.product_name, self.user.display_name)

    def cost(self):
        return self.quantity*self.product_price


class PurchaseSummary(Purchase):
    class Meta:
        proxy = True
        verbose_name = "Purchase Summary"
        verbose_name_plural = "Purchases Summary"


class StatsDisplay(models.Model):
    """ Admin-defined filters that can be shown as stats in frontend """
    title = models.CharField(max_length=30, blank=False)
    row_string = models.CharField(max_length=15, blank=True,
                                  help_text="This is shown on the right side of each stats row in the format "
                                            "'[row_string] [user_name]', so one example row could be "
                                            "'10x Coffee by Peter' with 'Coffee by' being the ROW_STRING")

    filter_category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True,
                                        help_text="If none, any category is used")
    filter_product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True,
                                       help_text="If none, any product is used")

    time_period = models.DurationField(default=datetime.timedelta(weeks=1), help_text="Duration over which "
                                                                                      "statistics are to be evaluated in the format 'WEEKS HOURS:MINUTES:SECONDS'")

    SORT_BY_NUM_PURCHASES = "NP"
    SORT_BY_TOTAL_COST_SHOW_RANK = "TC"
    SORT_BY_AND_SHOW_CHOICES = ((SORT_BY_NUM_PURCHASES, "Sort by and show number of purchases"),
                                (SORT_BY_TOTAL_COST_SHOW_RANK, "Sort by total cost and show rank"))
    sort_by_and_show = models.CharField(max_length=2,
                                        choices=SORT_BY_AND_SHOW_CHOICES,
                                        default=SORT_BY_NUM_PURCHASES)

    # A special boolean field that may only be True for one StatsDisplay
    # i.e. only one StatsDisplay can be the chosen one
    # Need to override save() for this
    show_by_default = models.BooleanField(
        help_text="Whether this should always be shown first. " \
                  "If not, it can be selected by cycling through the other ones, " \
                  "as long as any one is shown by default.")

    def save(self, *args, **kwargs):
        """Make sure that only one StatsDisplay is shown by default"""
        if self.show_by_default:
            queryset = StatsDisplay.objects.filter(show_by_default=True)
            if self.pk:
                # already exists
                queryset = queryset.exclude(pk=self.pk)
            if queryset.count() != 0:
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
