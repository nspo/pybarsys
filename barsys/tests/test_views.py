from decimal import Decimal
from unittest import mock

from django.contrib.messages import get_messages
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from barsys.forms import UserCreateForm, UserUpdateForm
from barsys.models import *
from pybarsys.settings import PybarsysPreferences

# EasyVerein behaviour is gated on PybarsysPreferences.EasyVerein.ACTIVE, a class
# attribute read from .env. Pin it explicitly per test rather than depend on .env.
ev_inactive = mock.patch.object(PybarsysPreferences.EasyVerein, "ACTIVE", False)
ev_active = mock.patch.object(PybarsysPreferences.EasyVerein, "ACTIVE", True)


class AdminViewSmokeTest(TestCase):
    """Assert all admin pages load without errors for a logged-in admin."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            "admin@example.com", "Admin", "password"
        )
        self.client.login(username="admin@example.com", password="password")

        self.cat = Category.objects.create(name="Drinks")
        self.product = Product.objects.create(
            category=self.cat, name="Cola", price="1.00", amount="0.5 l"
        )
        self.user = User.objects.create_user("user@example.com", "Regular User", "pw")
        self.purchase = Purchase.objects.create_from_product(
            self.product, user=self.admin, quantity=1
        )
        self.invoice = Invoice.objects.create_for_user(self.admin)
        self.payment = Payment.objects.create(user=self.admin, amount=Decimal("5.00"))
        self.statsdisplay = StatsDisplay.objects.create(title="Test Stats")
        self.pac_set = ProductAutochangeSet.objects.create(title="Test PAC Set")
        self.freeitem = FreeItem.objects.create(
            product=self.product, leftover_quantity=10
        )

    def _assert_200(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, f"Expected 200 for {url}")

    def _assert_redirects(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302, f"Expected 302 for {url}")

    def test_purchase_pages(self):
        pk = self.purchase.pk
        self._assert_200(reverse("admin_purchase_list"))
        self._assert_200(reverse("admin_purchase_new"))
        self._assert_200(reverse("admin_purchase_detail", kwargs={"pk": pk}))
        # invoiced purchases must not be editable (would corrupt invoice totals); delete shows confirmation page
        self._assert_redirects(reverse("admin_purchase_update", kwargs={"pk": pk}))
        self._assert_200(reverse("admin_purchase_delete", kwargs={"pk": pk}))
        # uninvoiced purchase should be editable and deletable
        loose = Purchase.objects.create_from_product(
            self.product, user=self.admin, quantity=1
        )
        self._assert_200(reverse("admin_purchase_update", kwargs={"pk": loose.pk}))
        self._assert_200(reverse("admin_purchase_delete", kwargs={"pk": loose.pk}))

    def test_user_pages(self):
        pk = self.user.pk
        self._assert_200(reverse("admin_user_list"))
        self._assert_200(reverse("admin_user_export"))
        self._assert_200(reverse("admin_user_new"))
        self._assert_200(reverse("admin_user_detail", kwargs={"pk": pk}))
        self._assert_200(reverse("admin_user_update", kwargs={"pk": pk}))
        self._assert_200(reverse("admin_user_delete", kwargs={"pk": pk}))
        self._assert_200(reverse("admin_user_payment_reminder_mail", kwargs={"pk": pk}))
        self._assert_redirects(
            reverse("admin_user_payment_reminder_send", kwargs={"pk": pk})
        )

    def test_category_pages(self):
        pk = self.cat.pk
        self._assert_200(reverse("admin_category_list"))
        self._assert_200(reverse("admin_category_new"))
        self._assert_200(reverse("admin_category_detail", kwargs={"pk": pk}))
        self._assert_200(reverse("admin_category_update", kwargs={"pk": pk}))
        self._assert_200(reverse("admin_category_delete", kwargs={"pk": pk}))

    def test_product_pages(self):
        pk = self.product.pk
        self._assert_200(reverse("admin_product_list"))
        self._assert_200(reverse("admin_product_new"))
        self._assert_200(reverse("admin_product_detail", kwargs={"pk": pk}))
        self._assert_200(reverse("admin_product_update", kwargs={"pk": pk}))
        self._assert_200(reverse("admin_product_delete", kwargs={"pk": pk}))

    def test_payment_pages(self):
        pk = self.payment.pk
        self._assert_200(reverse("admin_payment_list"))
        self._assert_200(reverse("admin_payment_export"))
        self._assert_200(reverse("admin_payment_new"))
        self._assert_200(reverse("admin_payment_detail", kwargs={"pk": pk}))
        self._assert_200(reverse("admin_payment_update", kwargs={"pk": pk}))
        self._assert_200(reverse("admin_payment_delete", kwargs={"pk": pk}))

    @ev_inactive
    def test_invoice_pages(self):
        pk = self.invoice.pk
        self._assert_200(reverse("admin_invoice_list"))
        self._assert_200(reverse("admin_invoice_new"))
        self._assert_200(reverse("admin_invoice_detail", kwargs={"pk": pk}))
        self._assert_200(reverse("admin_invoice_mail", kwargs={"pk": pk}))
        self._assert_200(reverse("admin_invoice_delete", kwargs={"pk": pk}))
        self._assert_redirects(reverse("admin_invoice_resend", kwargs={"pk": pk}))

    @ev_active
    def test_easyverein_pages(self):
        # The EasyVerein admin pages load (GET does not touch the EasyVerein API).
        self._assert_200(reverse("admin_easyverein_invoice_new"))
        self._assert_200(reverse("admin_easyverein_sync_users"))
        self._assert_200(reverse("admin_site_settings"))

    @ev_active
    def test_invoice_new_redirects_to_easyverein_when_active(self):
        # When EasyVerein is active, the normal invoice page redirects to the EV flow,
        # preserving the ?user= preselection.
        self.assertRedirects(
            self.client.get(reverse("admin_invoice_new")),
            reverse("admin_easyverein_invoice_new"),
        )
        self.assertRedirects(
            self.client.get(reverse("admin_invoice_new") + f"?user={self.user.pk}"),
            reverse("admin_easyverein_invoice_new") + f"?user={self.user.pk}",
            fetch_redirect_response=False,
        )

    def test_statsdisplay_pages(self):
        pk = self.statsdisplay.pk
        self._assert_200(reverse("admin_statsdisplay_list"))
        self._assert_200(reverse("admin_statsdisplay_new"))
        self._assert_200(reverse("admin_statsdisplay_detail", kwargs={"pk": pk}))
        self._assert_200(reverse("admin_statsdisplay_update", kwargs={"pk": pk}))
        self._assert_200(reverse("admin_statsdisplay_delete", kwargs={"pk": pk}))

    def test_productautochangeset_pages(self):
        pk = self.pac_set.pk
        self._assert_200(reverse("admin_productautochangeset_list"))
        self._assert_200(reverse("admin_productautochangeset_new"))
        self._assert_200(
            reverse("admin_productautochangeset_update", kwargs={"pk": pk})
        )
        self._assert_200(
            reverse("admin_productautochangeset_delete", kwargs={"pk": pk})
        )
        self._assert_redirects(
            reverse("admin_productautochangeset_execute", kwargs={"pk": pk})
        )
        self._assert_redirects(
            reverse("admin_productautochangeset_import", kwargs={"pk": pk})
        )

    def test_freeitem_pages(self):
        pk = self.freeitem.pk
        self._assert_200(reverse("admin_freeitem_list"))
        self._assert_200(reverse("admin_freeitem_new"))
        self._assert_200(reverse("admin_freeitem_update", kwargs={"pk": pk}))
        self._assert_200(reverse("admin_freeitem_delete", kwargs={"pk": pk}))

    def test_statistics_pages(self):
        self._assert_200(reverse("admin_purchase_statistics_by_category"))
        self._assert_200(reverse("admin_purchase_statistics_by_product"))
        self._assert_200(reverse("admin_purchase_statistics_by_user"))
        self._assert_200(reverse("admin_user_statistics_by_account_balance"))

    def test_unauthenticated_redirects(self):
        self.client.logout()
        # Statistics pages are included because they expose names and balances, and
        # the account-balance one was reachable without logging in for a while.
        for name in (
            "admin_user_list",
            "admin_purchase_statistics_by_category",
            "admin_purchase_statistics_by_product",
            "admin_purchase_statistics_by_user",
            "admin_user_statistics_by_account_balance",
        ):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, "{} is public".format(name))


class MainKioskSmokeTest(TestCase):
    """Assert key kiosk pages load without login (kiosk is publicly accessible)."""

    def setUp(self):
        cat = Category.objects.create(name="Drinks")
        self.product = Product.objects.create(
            category=cat, name="Cola", price="1.00", amount="0.5 l"
        )
        self.user = User.objects.create_user("kiosk@example.com", "Kiosk User")

    def _assert_200(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, f"Expected 200 for {url}")

    def test_user_list(self):
        self._assert_200(reverse("main_user_list"))

    def test_user_purchase(self):
        self._assert_200(
            reverse("main_user_purchase", kwargs={"user_id": self.user.pk})
        )

    def test_user_history(self):
        self._assert_200(reverse("main_user_history", kwargs={"user_id": self.user.pk}))

    def test_multibuy_user_list(self):
        self._assert_200(reverse("main_user_list_multibuy"))

    def test_purchase_single_user(self):
        response = self.client.post(
            reverse("main_user_purchase", kwargs={"user_id": self.user.pk}),
            {"user_id": self.user.pk, "product_id": self.product.pk, "quantity": 2},
        )
        self.assertRedirects(response, reverse("main_user_list"))
        self.assertEqual(Purchase.objects.filter(user=self.user).count(), 1)
        self.assertEqual(Purchase.objects.get(user=self.user).quantity, 2)

    def test_purchase_multibuy(self):
        user2 = User.objects.create_user("kiosk2@example.com", "Kiosk User 2")
        user_pkey_str = f"{self.user.pk}/{user2.pk}"
        response = self.client.post(
            reverse(
                "main_user_purchase_multibuy",
                kwargs={"user_pkey_str": user_pkey_str},
            ),
            {"product_id": self.product.pk, "quantity": 1},
        )
        self.assertRedirects(response, reverse("main_user_list"))
        self.assertEqual(Purchase.objects.filter(user=self.user).count(), 1)
        self.assertEqual(Purchase.objects.filter(user=user2).count(), 1)


@ev_inactive
class InvoiceCreateMailTest(TestCase):
    """Test that invoice creation sends mail and creates the invoice."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            "admin@example.com", "Admin", "password"
        )
        self.client.login(username="admin@example.com", password="password")

        cat = Category.objects.create(name="Drinks")
        prod = Product.objects.create(
            category=cat, name="Cola", price="1.00", amount="0.5 l"
        )
        self.user = User.objects.create_user("user@example.com", "Regular User")
        Purchase.objects.create_from_product(prod, user=self.user, quantity=3)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_invoice_created_and_mail_sent(self):
        response = self.client.post(
            reverse("admin_invoice_new"),
            {
                "users": [self.user.pk],
                "send_invoices": True,
                "send_dependant_notifications": True,
                "send_payment_reminders": True,
                "autolock_accounts": False,
                "comment": "",
                "create": "Create",
            },
        )
        self.assertRedirects(response, reverse("admin_invoice_list"))
        self.assertEqual(Invoice.objects.filter(recipient=self.user).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("user@example.com", mail.outbox[0].to)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_invoice_with_dependant_notifications(self):
        # dependant1 has purchases -> gets a notification; dependant2 does not -> no mail
        dependant1 = User.objects.create_user("dep1@example.com", "Dependant One")
        dependant1.purchases_paid_by_other = self.user
        dependant1.save()
        dependant2 = User.objects.create_user("dep2@example.com", "Dependant Two")
        dependant2.purchases_paid_by_other = self.user
        dependant2.save()

        prod = Product.objects.get(name="Cola")
        Purchase.objects.create_from_product(prod, user=dependant1, quantity=2)

        response = self.client.post(
            reverse("admin_invoice_new"),
            {
                "users": [self.user.pk],
                "send_invoices": True,
                "send_dependant_notifications": True,
                "send_payment_reminders": False,
                "autolock_accounts": False,
                "comment": "",
                "create": "Create",
            },
        )
        self.assertRedirects(response, reverse("admin_invoice_list"))
        # payer gets invoice mail, dependant1 gets purchase notification, dependant2 gets nothing
        self.assertEqual(len(mail.outbox), 2)
        all_recipients = [addr for msg in mail.outbox for addr in msg.to]
        self.assertIn("user@example.com", all_recipients)
        self.assertIn("dep1@example.com", all_recipients)
        self.assertNotIn("dep2@example.com", all_recipients)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_autolock_trigger(self):
        post_kwargs = {
            "users": [self.user.pk],
            "send_invoices": True,
            "send_dependant_notifications": False,
            "send_payment_reminders": False,
            "autolock_accounts": True,
            "comment": "",
            "create": "Create",
        }
        # Cycle 1: balance_before=0 (no prior invoices) -> NOT autolocked despite large purchase
        cat = Category.objects.get(name="Drinks")
        prod = Product.objects.create(
            category=cat, name="Beer", price="200.00", amount="0.5 l"
        )
        Purchase.objects.create_from_product(prod, user=self.user, quantity=1)
        self.client.post(reverse("admin_invoice_new"), post_kwargs)
        self.assertEqual(len(mail.outbox), 1)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_autolocked)
        self.assertEqual(self.user.account_balance(), Decimal("-203.00"))

        # Cycle 2: balance_before=-203 (below -100), autolock must trigger
        Purchase.objects.create_from_product(prod, user=self.user, quantity=1)
        self.client.post(reverse("admin_invoice_new"), post_kwargs)
        self.assertEqual(len(mail.outbox), 2)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_autolocked)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_autolock_release(self):
        post_kwargs = {
            "users": [self.user.pk],
            "send_invoices": True,
            "send_dependant_notifications": False,
            "send_payment_reminders": False,
            "autolock_accounts": True,
            "comment": "",
            "create": "Create",
        }
        cat = Category.objects.get(name="Drinks")
        expensive = Product.objects.create(
            category=cat, name="Expensive", price="200.00", amount="1 l"
        )
        cola = Product.objects.get(name="Cola")

        # Cycle 1: balance_before=0 (no prior invoices) -> NOT autolocked despite large purchase
        Purchase.objects.create_from_product(expensive, user=self.user, quantity=1)
        self.client.post(reverse("admin_invoice_new"), post_kwargs)
        self.assertEqual(len(mail.outbox), 1)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_autolocked)
        self.assertEqual(self.user.account_balance(), Decimal("-203.00"))

        # Cycle 2: balance_before=-203 < -100 and balance_after=-205 < -100 -> autolocked
        Purchase.objects.create_from_product(cola, user=self.user, quantity=2)
        self.client.post(reverse("admin_invoice_new"), post_kwargs)
        self.assertEqual(len(mail.outbox), 2)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_autolocked)
        self.assertEqual(self.user.account_balance(), Decimal("-205.00"))

        # Cycle 3: payment clears debt -> balance_after=295 > -100 -> auto-released
        Payment.objects.create(user=self.user, amount=Decimal("500.00"))
        self.client.post(reverse("admin_invoice_new"), post_kwargs)
        self.assertEqual(len(mail.outbox), 3)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_autolocked)
        self.assertEqual(self.user.account_balance(), Decimal("295.00"))


@ev_active
class UserCreateFormEasyVereinTest(TestCase):
    """With EasyVerein active, self-paying buyers must be attached to an EV contact."""

    base_data = {
        "email": "new@example.com",
        "display_name": "New User",
        "is_active": "on",
        "is_buyer": "on",
    }
    ev_url = "https://easyverein.com/api/v2.0/contact-details/123"

    def test_self_paying_buyer_requires_ev_link(self):
        form = UserCreateForm(data=self.base_data)
        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)

    def test_self_paying_buyer_with_ev_link_is_valid(self):
        form = UserCreateForm(
            data={**self.base_data, "easyverein_contact_details_url": self.ev_url}
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_non_buyer_without_ev_link_is_valid(self):
        form = UserCreateForm(data={**self.base_data, "is_buyer": ""})
        self.assertTrue(form.is_valid(), form.errors)


class BalanceTransferFormTest(TestCase):
    """UserUpdateForm gates the balance transfer that turning A into a dependant causes.

    EasyVerein is pinned per method, not on the class: mock.patch appends to an already
    decorated method's patch list instead of nesting, so a class decorator would win
    over a method one.
    """

    def setUp(self):
        cat = Category.objects.create(name="Drinks")
        self.product = Product.objects.create(
            category=cat, name="Cola", price="1.00", amount="0.5 l"
        )
        self.a = User.objects.create_user("a@example.com", "Aaa", "pw")
        self.b = User.objects.create_user("b@example.com", "Bbb", "pw")

    def buy(self, user, quantity):
        Purchase.objects.create_from_product(self.product, user=user, quantity=quantity)

    def owe(self, amount=20):
        """Give A an invoiced debt, i.e. a real negative account balance."""
        self.buy(self.a, amount)
        Invoice.objects.create_for_user(self.a)

    def form_data(self, **extra):
        return {
            "email": self.a.email,
            "display_name": self.a.display_name,
            "password1": "",
            "password2": "",
            "purchases_paid_by_other": self.b.pk,
            "is_active": "on",
            "is_buyer": "on",
            **extra,
        }

    @ev_inactive
    def test_no_confirmation_field_when_just_opening_the_page(self):
        """A debt alone must not put a context-free checkbox on every edit page."""
        self.owe(20)

        form = UserUpdateForm(instance=self.a)

        self.assertNotIn("confirm_balance_transfer", form.fields)

    @ev_inactive
    def test_no_confirmation_field_when_no_payer_is_assigned(self):
        self.owe(20)

        form = UserUpdateForm(
            instance=self.a, data=self.form_data(purchases_paid_by_other="")
        )

        self.assertNotIn("confirm_balance_transfer", form.fields)
        self.assertTrue(form.is_valid(), form.errors)

    @ev_inactive
    def test_no_confirmation_field_without_a_balance(self):
        form = UserUpdateForm(instance=self.a, data=self.form_data())
        self.assertNotIn("confirm_balance_transfer", form.fields)
        self.assertTrue(form.is_valid(), form.errors)

    @ev_inactive
    def test_transfer_must_be_confirmed(self):
        self.owe(20)

        form = UserUpdateForm(instance=self.a, data=self.form_data())

        self.assertFalse(form.is_valid())
        self.assertIn("confirm_balance_transfer", form.errors)
        self.assertIn("Bbb", str(form.errors["confirm_balance_transfer"]))

    @ev_inactive
    def test_confirmed_transfer_passes_the_model_balance_check(self):
        """User.clean() would refuse this; the confirmation flag lets validation past."""
        self.owe(20)

        form = UserUpdateForm(
            instance=self.a, data=self.form_data(confirm_balance_transfer="on")
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.instance._balance_moves_to_payer)

    @ev_inactive
    def test_unbilled_purchases_count_towards_the_transfer(self):
        self.owe(20)
        self.buy(self.a, 5)  # not invoiced yet

        form = UserUpdateForm(instance=self.a, data=self.form_data())

        self.assertEqual(self.a.open_balance(), Decimal("-25.00"))
        self.assertFalse(form.is_valid())
        # format it the same way the message does - the rendering is locale dependent
        self.assertIn(
            currency(Decimal("-25.00")), str(form.errors["confirm_balance_transfer"])
        )

    @ev_inactive
    def test_user_paying_for_others_is_refused_by_the_model_not_by_us(self):
        """Even with a balance, the dependants error must be what the admin sees."""
        self.owe(20)
        dependant = User.objects.create_user("dep@example.com", "Dep", "pw")
        dependant.purchases_paid_by_other = self.a
        dependant.save()

        form = UserUpdateForm(
            instance=self.a, data=self.form_data(confirm_balance_transfer="on")
        )

        self.assertFalse(form.is_valid())
        self.assertNotIn("confirm_balance_transfer", form.errors)
        self.assertIn("pays for the following users", str(form.errors))

    @ev_active
    def test_payer_without_easyverein_link_is_refused(self):
        self.owe(20)
        self.a.easyverein_contact_details_url = "https://ev.example/contact/1"
        self.a.save()

        form = UserUpdateForm(
            instance=self.a, data=self.form_data(confirm_balance_transfer="on")
        )

        self.assertFalse(form.is_valid())
        # reported on the field the admin has to change, so it gets highlighted
        self.assertIn(
            "not attached to an EasyVerein contact",
            str(form.errors["purchases_paid_by_other"]),
        )
        # and not drowned out by the model check describing the very balance we move
        self.assertNotIn("Cannot make user a dependant", str(form.errors))
        # nothing to confirm while the payer cannot receive the balance, so the
        # checkbox must not linger without its explanation
        self.assertNotIn("confirm_balance_transfer", form.fields)

    @ev_inactive
    def test_settles_without_confirmation_when_nothing_changes_hands(self):
        """Open items can cancel out while User.clean() still refuses the change.

        The gate must follow what actually blocks, not the net amount - otherwise the
        admin gets a model error they cannot resolve from this form.
        """
        self.owe(20)
        Payment.objects.create(user=self.a, amount=Decimal("20.00"))  # paid, unbilled

        form = UserUpdateForm(instance=self.a, data=self.form_data())

        self.assertEqual(self.a.open_balance(), Decimal("0"))
        self.assertTrue(form.needs_settlement())
        # nothing moves, so there is nothing to confirm
        self.assertNotIn("confirm_balance_transfer", form.fields)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.instance._balance_moves_to_payer)

    @ev_inactive
    def test_confirmation_request_is_not_drowned_out_by_the_model_check(self):
        self.owe(20)
        Payment.objects.create(user=self.a, amount=Decimal("5.00"))  # unbilled

        form = UserUpdateForm(instance=self.a, data=self.form_data())

        self.assertFalse(form.is_valid())
        self.assertIn("confirm_balance_transfer", form.errors)
        self.assertNotIn("Cannot make user a dependant", str(form.errors))


class BalanceTransferViewTest(TestCase):
    """End to end: making A a dependant of B moves A's balance onto B."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            "admin@example.com", "Admin", "password"
        )
        self.client.login(username="admin@example.com", password="password")
        cat = Category.objects.create(name="Drinks")
        self.product = Product.objects.create(
            category=cat, name="Cola", price="1.00", amount="0.5 l"
        )
        self.a = User.objects.create_user("a@example.com", "Aaa", "pw")
        self.b = User.objects.create_user("b@example.com", "Bbb", "pw")

    def post_conversion(self, **extra):
        return self.client.post(
            reverse("admin_user_update", kwargs={"pk": self.a.pk}),
            {
                "email": self.a.email,
                "display_name": self.a.display_name,
                "password1": "",
                "password2": "",
                "purchases_paid_by_other": self.b.pk,
                "is_active": "on",
                "is_buyer": "on",
                "confirm_balance_transfer": "on",
                **extra,
            },
            follow=True,
        )

    @ev_inactive
    def test_debt_is_moved_to_the_payer(self):
        Purchase.objects.create_from_product(self.product, user=self.a, quantity=20)
        Invoice.objects.create_for_user(self.a)  # A owes 20
        Purchase.objects.create_from_product(self.product, user=self.a, quantity=5)

        response = self.post_conversion()

        self.a.refresh_from_db()
        self.assertEqual(self.a.purchases_paid_by_other, self.b)
        self.assertEqual(self.a.account_balance(), Decimal("0"))
        # A is settled, B carries the debt as an unbilled payment
        payment_to = Payment.objects.get(user=self.b)
        self.assertEqual(payment_to.amount, Decimal("-25.00"))
        self.assertIsNone(payment_to.invoice)
        # sum-neutral: nothing created or destroyed
        self.assertEqual(Payment.objects.all().sum_amount(), Decimal("0"))
        self.assertIn("Moved", " ".join(str(m) for m in response.context["messages"]))

    @ev_inactive
    def test_credit_is_moved_to_the_payer_too(self):
        Purchase.objects.create_from_product(self.product, user=self.a, quantity=10)
        Payment.objects.create(user=self.a, amount=Decimal("30.00"))
        Invoice.objects.create_for_user(self.a)  # A is 20 in credit

        self.post_conversion()

        self.a.refresh_from_db()
        self.assertEqual(self.a.purchases_paid_by_other, self.b)
        self.assertEqual(self.a.account_balance(), Decimal("0"))
        # roles swap: B gets the credit
        self.assertEqual(
            Payment.objects.filter(user=self.b).get().amount, Decimal("20.00")
        )

    @ev_active
    def test_debt_is_moved_only_with_easyverein_active(self):
        """With EasyVerein on, the payer must be attached or the debt becomes stuck."""
        Purchase.objects.create_from_product(self.product, user=self.a, quantity=20)
        Invoice.objects.create_for_user(self.a)

        # B cannot be invoiced via EasyVerein, so moving the debt there would strand it
        self.post_conversion(easyverein_contact_details_url="")

        self.a.refresh_from_db()
        self.assertTrue(self.a.pays_themselves())
        self.assertEqual(self.a.account_balance(), Decimal("-20.00"))
        self.assertFalse(Payment.objects.filter(user=self.b).exists())

        # attaching B is all that was missing - the very same request now goes through
        self.b.easyverein_contact_details_url = "https://ev.example/contact/1"
        self.b.save()

        self.post_conversion(easyverein_contact_details_url="")

        self.a.refresh_from_db()
        self.assertEqual(self.a.purchases_paid_by_other, self.b)
        self.assertEqual(self.a.account_balance(), Decimal("0"))
        self.assertEqual(Payment.objects.get(user=self.b).amount, Decimal("-20.00"))
        self.assertEqual(Payment.objects.all().sum_amount(), Decimal("0"))

    @ev_inactive
    def test_open_items_that_cancel_out_are_still_settled(self):
        """A owes 20 and has just paid 20 in cash, not yet invoiced.

        The net amount is 0, but User.clean() still refuses the change - so the open
        items have to be billed anyway. Nothing changes hands, so nothing to confirm.
        """
        Purchase.objects.create_from_product(self.product, user=self.a, quantity=20)
        Invoice.objects.create_for_user(self.a)
        Payment.objects.create(user=self.a, amount=Decimal("20.00"))

        self.post_conversion(confirm_balance_transfer="")

        self.a.refresh_from_db()
        self.assertEqual(self.a.purchases_paid_by_other, self.b)
        self.assertEqual(self.a.account_balance(), Decimal("0"))
        self.assertFalse(self.a.payments().unbilled().exists())
        self.assertEqual(Payment.objects.get(user=self.b).amount, Decimal("0"))

    @ev_inactive
    def test_credit_covering_an_unbilled_purchase_is_not_stranded(self):
        """A has 5 credit and an unbilled purchase of 5 - a net amount of 0.

        Without settling, the purchase would be billed to B while the credit stayed
        stuck on A, who can never be invoiced again.
        """
        Payment.objects.create(user=self.a, amount=Decimal("5.00"))
        Invoice.objects.create_for_user(self.a)
        self.assertEqual(self.a.account_balance(), Decimal("5.00"))
        Purchase.objects.create_from_product(self.product, user=self.a, quantity=5)

        self.post_conversion(confirm_balance_transfer="")

        self.a.refresh_from_db()
        self.assertEqual(self.a.purchases_paid_by_other, self.b)
        self.assertEqual(self.a.account_balance(), Decimal("0"))
        # the credit paid for the purchase, so B is charged nothing
        self.assertEqual(Payment.objects.get(user=self.b).amount, Decimal("0"))

    @ev_inactive
    def test_the_payer_is_billed_for_the_moved_balance(self):
        Purchase.objects.create_from_product(self.product, user=self.a, quantity=20)
        Invoice.objects.create_for_user(self.a)

        self.post_conversion()
        Invoice.objects.create_for_user(self.b)

        self.assertEqual(self.b.account_balance(), Decimal("-20.00"))


class AdminViewsRequireAdminTest(TestCase):
    """Views that override dispatch() must still check permissions first.

    UserPassesTestMixin only runs its test inside super().dispatch(), so anything an
    override does beforehand happens for anonymous visitors too.
    """

    def setUp(self):
        payer = User.objects.create_user("payer@example.com", "PayerName", "pw")
        self.dependant = User.objects.create_user("dep@example.com", "DepName", "pw")
        self.dependant.purchases_paid_by_other = payer
        self.dependant.save()
        self.clean_user = User.objects.create_user(
            "clean@example.com", "CleanOne", "pw"
        )

    def assert_sends_to_login(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    @ev_inactive
    def test_settle_balance_refusals_do_not_leak_to_anonymous_users(self):
        # both refusal paths return before super().dispatch() and name the user
        for user in (self.dependant, self.clean_user):
            self.assert_sends_to_login(
                reverse("admin_user_settle_balance", kwargs={"pk": user.pk})
            )

    @ev_active
    def test_invoice_create_easyverein_redirect_requires_admin(self):
        self.assert_sends_to_login(reverse("admin_invoice_new"))


class UserSettleBalanceViewTest(TestCase):
    """Manual balance correction: write a balance off without billing anyone.

    Must work with EasyVerein both on and off - it is the escape hatch for users
    that cannot be invoiced at all.
    """

    def setUp(self):
        self.admin = User.objects.create_superuser(
            "admin@example.com", "Admin", "password"
        )
        self.client.login(username="admin@example.com", password="password")
        cat = Category.objects.create(name="Drinks")
        # 1.00 per unit, so quantity == euros
        self.product = Product.objects.create(
            category=cat, name="Cola", price="1.00", amount="0.5 l"
        )
        self.user = User.objects.create_user("debtor@example.com", "Debtor", "pw")

    def url(self, user=None):
        return reverse(
            "admin_user_settle_balance", kwargs={"pk": (user or self.user).pk}
        )

    def buy(self, quantity, user=None):
        Purchase.objects.create_from_product(
            self.product, user=user or self.user, quantity=quantity
        )

    def test_confirmation_page_shows_the_projected_correction(self):
        self.buy(20)
        Invoice.objects.create_for_user(self.user)  # carried balance of -20
        self.buy(5)  # still unbilled

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["balance"], Decimal("-20.00"))
        self.assertEqual(response.context["open_purchases"], Decimal("5.00"))
        self.assertEqual(response.context["settlement"], Decimal("25.00"))

    @ev_active
    def test_settles_with_easyverein_active(self):
        self.buy(20)
        Invoice.objects.create_for_user(self.user)

        response = self.client.post(self.url(), {"reason": "User has died"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.user.account_balance(), Decimal("0"))
        payment = Payment.objects.get(comment__startswith="Manual balance correction")
        self.assertEqual(payment.amount, Decimal("20.00"))
        self.assertEqual(payment.payment_method, Payment.PAYMENT_METHOD_OTHER)
        # a correction is a real booking, so it must survive its invoice
        self.assertFalse(payment.is_virtual_payment)
        self.assertEqual(payment.comment, "Manual balance correction: User has died")
        self.assertEqual(
            payment.invoice.comment, "Manual balance correction: User has died"
        )

    @ev_inactive
    def test_settles_with_easyverein_inactive(self):
        self.buy(20)
        Invoice.objects.create_for_user(self.user)

        self.client.post(self.url(), {"reason": "Moved away, unreachable"})

        self.assertEqual(self.user.account_balance(), Decimal("0"))
        self.assertTrue(
            Payment.objects.filter(comment__startswith="Manual balance").exists()
        )

    def test_reason_is_mandatory(self):
        self.buy(20)
        Invoice.objects.create_for_user(self.user)

        response = self.client.post(self.url(), {"reason": "   "})

        self.assertEqual(response.status_code, 200)  # redisplayed with errors
        self.assertIn("reason", response.context["form"].errors)
        self.assertEqual(self.user.account_balance(), Decimal("-20.00"))
        self.assertEqual(Invoice.objects.filter(recipient=self.user).count(), 1)

    def test_long_reason_is_shortened_on_the_payment_but_kept_on_the_invoice(self):
        self.buy(20)
        Invoice.objects.create_for_user(self.user)
        reason = (
            "User has died in August; the remaining balance was written off "
            "following the board decision of 2026-09-01, see the meeting minutes"
        )

        self.client.post(self.url(), {"reason": reason})

        payment = Payment.objects.get(comment__startswith="Manual balance correction")
        max_length = Payment._meta.get_field("comment").max_length
        self.assertLessEqual(len(payment.comment), max_length)
        self.assertTrue(payment.comment.endswith("…"))
        # the invoice keeps every word
        self.assertEqual(
            payment.invoice.comment, "Manual balance correction: " + reason
        )

    def _messages(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def test_nothing_to_settle_is_refused(self):
        response = self.client.get(self.url())

        self.assertRedirects(
            response, reverse("admin_user_detail", kwargs={"pk": self.user.pk})
        )
        self.assertFalse(Invoice.objects.exists())
        self.assertIn("Nothing to settle", " ".join(self._messages(response)))

    def test_dependant_is_refused(self):
        payer = User.objects.create_user("payer@example.com", "Payer", "pw")
        self.user.purchases_paid_by_other = payer
        self.user.save()
        self.buy(20)  # billed to the payer, not to this user

        response = self.client.post(self.url(), {"reason": "whatever"})

        self.assertRedirects(
            response, reverse("admin_user_detail", kwargs={"pk": self.user.pk})
        )
        self.assertFalse(Invoice.objects.exists())
        # must be refused for being a dependant - not merely because a dependant
        # happens to have nothing of their own to settle
        self.assertIn(
            "does not pay for their own purchases", " ".join(self._messages(response))
        )
