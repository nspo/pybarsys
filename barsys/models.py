from django.db import models
from django.contrib.auth.models import (
    BaseUserManager, AbstractBaseUser
)
from django.db.models import F


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


class User(AbstractBaseUser):
    email = models.EmailField(max_length=255, unique=True, blank=False)

    display_name = models.CharField(max_length=40, unique=True, blank=False)

    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    is_buyer = models.BooleanField(default=True)

    purchases_paid_by = models.ForeignKey("self", on_delete=models.PROTECT, default=None, null=True, blank=True)

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
    name = models.CharField(max_length=40, unique=True, blank=False)
    price = models.DecimalField(max_digits=5, decimal_places=2, blank=False, null=False)
    amount = models.CharField(max_length=10, blank=False)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, null=False)

    def __str__(self):
        return "{} ({}, {})".format(self.name, self.amount, self.price)


class Invoice(models.Model):
    # Dates
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)


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

    def __str__(self):
        return "{}x {} ({})".format(self.quantity, self.product_name, self.user.display_name)


# Admin-defined filters that can be shown as stats in frontend
class StatsDisplay(models.Model):
    title = models.CharField(max_length=30, blank=False)
    row_string = models.CharField(max_length=15, blank=True,
                                  help_text="This is shown on the right side of each stats row in the format "\
                                  "'[row_string] [user_name]', so one example row could be "\
                                  "'10x Coffee by Peter' with 'Coffee by' being the ROW_STRING")

    filter_category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True,
                                        help_text="If none, any category is used")
    filter_product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True,
                                       help_text="If none, any product is used")

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
        help_text="Whether this should always be shown first. "\
                  "If not, it can be selected by cycling through the other ones, "\
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

    def get_renderable(self=None):
        """Create a list of dicts for all StatsDisplays that can be rendered by view more easily"""
        stats_elements = []

        all_displays = StatsDisplay.objects.order_by("-show_by_default")
        for index, stat in enumerate(all_displays):
            stats_element = {}
            stats_element["stats_id"] = "stats_{}".format(stat.pk)
            stats_element["show_by_default"] = stat.show_by_default
            stats_element["title"] = stat.title

            # construct query step by step
            users = User.objects
            if stat.filter_category:
                users = users.filter(purchase__product_category=stat.filter_category.name)
            if stat.filter_product:
                users = users.filter(purchase__product_name=stat.filter_product.name)

            stats_element["rows"] = []
            if stat.sort_by_and_show == StatsDisplay.SORT_BY_NUM_PURCHASES:
                top_five = users.annotate(num_purchases=models.Sum("purchase__quantity")).order_by("-num_purchases")[:5]
                for user in top_five:
                    stats_element["rows"].append({"left": "{}x".format(user.num_purchases),
                                                  "right": "{} {}".format(stat.row_string, user.display_name)})
            else:
                top_five = users.annotate(total_cost=models.Sum(F("purchase__quantity")*F("purchase__product_price"))).\
                    order_by("total_cost")[:5]
                for u_index, user in enumerate(top_five):
                    stats_element["rows"].append({"left": "{}.".format(u_index+1),
                                                  "right": "{} {}".format(stat.row_string, user.display_name)})

            if index + 1 < len(all_displays):
                # toggle next one on
                stats_element["toggle_other_on"] = "stats_{}".format(all_displays[index+1].pk)
            else:
                # toggle first one on
                stats_element["toggle_other_on"] = "stats_{}".format(all_displays[0].pk)

            stats_elements.append(stats_element)

        return stats_elements
