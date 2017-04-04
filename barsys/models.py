from django.db import models
from django.contrib.auth.models import (
    BaseUserManager, AbstractBaseUser
)


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
        return self.email

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

    def get_products(self):
        return Product.objects.filter(category__pk=self.pk)

class Product(models.Model):
    name = models.CharField(max_length=40, unique=True, blank=False)
    price = models.DecimalField(max_digits=5, decimal_places=2, blank=False, null=False)
    amount = models.CharField(max_length=10, blank=False)
    category = models.ForeignKey(Category, null=False)

    def __str__(self):
        return "{}, Price: {}".format(self.name, self.price)


# Create your models here.
