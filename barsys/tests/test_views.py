from decimal import Decimal

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from barsys.models import *


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

    def test_invoice_pages(self):
        pk = self.invoice.pk
        self._assert_200(reverse("admin_invoice_list"))
        self._assert_200(reverse("admin_invoice_new"))
        self._assert_200(reverse("admin_invoice_detail", kwargs={"pk": pk}))
        self._assert_200(reverse("admin_invoice_mail", kwargs={"pk": pk}))
        self._assert_200(reverse("admin_invoice_delete", kwargs={"pk": pk}))
        self._assert_redirects(reverse("admin_invoice_resend", kwargs={"pk": pk}))

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
        response = self.client.get(reverse("admin_user_list"))
        self.assertEqual(response.status_code, 302)


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
        # dependant1 has purchases → gets a notification; dependant2 does not → no mail
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
        # Cycle 1: balance_before=0 (no prior invoices) → NOT autolocked despite large purchase
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

        # Cycle 1: balance_before=0 (no prior invoices) → NOT autolocked despite large purchase
        Purchase.objects.create_from_product(expensive, user=self.user, quantity=1)
        self.client.post(reverse("admin_invoice_new"), post_kwargs)
        self.assertEqual(len(mail.outbox), 1)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_autolocked)
        self.assertEqual(self.user.account_balance(), Decimal("-203.00"))

        # Cycle 2: balance_before=-203 < -100 and balance_after=-205 < -100 → autolocked
        Purchase.objects.create_from_product(cola, user=self.user, quantity=2)
        self.client.post(reverse("admin_invoice_new"), post_kwargs)
        self.assertEqual(len(mail.outbox), 2)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_autolocked)
        self.assertEqual(self.user.account_balance(), Decimal("-205.00"))

        # Cycle 3: payment clears debt → balance_after=295 > -100 → auto-released
        Payment.objects.create(user=self.user, amount=Decimal("500.00"))
        self.client.post(reverse("admin_invoice_new"), post_kwargs)
        self.assertEqual(len(mail.outbox), 3)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_autolocked)
        self.assertEqual(self.user.account_balance(), Decimal("295.00"))
