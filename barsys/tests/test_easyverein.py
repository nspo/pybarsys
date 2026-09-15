from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase
from easyverein.models import ContactDetails

from barsys import view_helpers, views
from barsys.forms import SiteSettingsForm
from barsys.models import Category, Invoice, Payment, Product, Purchase, User
from barsys.views import (
    _ev_clean_name,
    _ev_match_contacts,
    _ev_rank_contacts_for_name,
    _ev_suggest_matches,
)
from pybarsys.settings import PybarsysPreferences

ev_active = mock.patch.object(PybarsysPreferences.EasyVerein, "ACTIVE", True)
ev_inactive = mock.patch.object(PybarsysPreferences.EasyVerein, "ACTIVE", False)


def _contact(contact_id: int, first: str, last: str) -> ContactDetails:
    return ContactDetails.model_validate(
        {"id": contact_id, "firstName": first, "familyName": last}
    )


class EasyVereinMatchingTest(SimpleTestCase):
    """Pure name-matching/ranking helpers (no DB, no EasyVerein API)."""

    def setUp(self):
        self.max = _contact(1, "Max", "Müller")
        self.moritz = _contact(2, "Moritz", "Müller")
        self.anna = _contact(3, "Anna", "Schmidt")
        self.contacts = [self.max, self.moritz, self.anna]

    def test_match_unique(self):
        matches, same_last = _ev_match_contacts(self.contacts, "Anna Schmidt")
        self.assertEqual(matches, [self.anna])
        self.assertEqual(same_last, [self.anna])

    def test_match_tie_break_by_longer_prefix(self):
        # "Max"/"Moritz" both start with "m"; prefix lengthens to disambiguate to Max.
        matches, same_last = _ev_match_contacts(self.contacts, "Max Müller")
        self.assertEqual(matches, [self.max])
        self.assertEqual(same_last, [self.max, self.moritz])

    def test_match_same_family_backup_when_no_first_match(self):
        matches, same_last = _ev_match_contacts(self.contacts, "Zacharias Müller")
        self.assertEqual(matches, [])
        self.assertEqual(same_last, [self.max, self.moritz])

    def test_match_no_family_match(self):
        matches, same_last = _ev_match_contacts(self.contacts, "John Doe")
        self.assertEqual(matches, [])
        self.assertEqual(same_last, [])

    def test_rank_three_tiers_no_duplication_and_complete(self):
        ranked = _ev_rank_contacts_for_name(self.contacts, "Max Müller")
        ranked_contacts = [row["contact"] for row in ranked]
        # full match, then same-family-name, then everyone else - this exact ordered
        # equality also proves no duplication and complete coverage.
        self.assertEqual(ranked_contacts, [self.max, self.moritz, self.anna])
        self.assertEqual([row["is_match"] for row in ranked], [True, False, False])
        self.assertIn(f"/contact-details/{self.max.id}", ranked[0]["url"])

    def test_suggest_high_and_low_buckets(self):
        users = [
            SimpleNamespace(display_name="Max Müller"),
            SimpleNamespace(display_name="Zacharias Müller"),
        ]
        result = _ev_suggest_matches(self.contacts, users)
        # Max -> unique full match -> high, pre-checked
        self.assertEqual([s["contact"] for s in result["high"]], [self.max])
        self.assertTrue(result["high"][0]["checked"])
        # Zacharias -> no first-name match -> low, both Müllers as weak hints, unchecked
        self.assertEqual([s["contact"] for s in result["low"]], [self.max, self.moritz])
        self.assertFalse(any(s["checked"] for s in result["low"]))


class EasyVereinNameCleanTest(SimpleTestCase):
    """Nickname stripping in _ev_clean_name."""

    def test_stripping(self):
        self.assertEqual(_ev_clean_name('Jessica "JiCode" Macbeth'), "Jessica Macbeth")
        self.assertEqual(_ev_clean_name("First (Nick) Last"), "First Last")
        self.assertEqual(_ev_clean_name("First - Nick - Last"), "First Last")


class InvoiceDeleteVirtualPaymentTest(TestCase):
    """Invoice.delete() must remove its virtual payments but keep real ones (un-billed)."""

    def setUp(self):
        self.user = User.objects.create_user("u@example.com", "U", "pw")

    def _make_invoice_with_payments(self):
        invoice = Invoice.objects.create(
            recipient=self.user,
            amount_purchases=Decimal("0"),
            amount_payments=Decimal("0"),
        )
        virtual = Payment.objects.create(
            user=self.user,
            amount=Decimal("5"),
            invoice=invoice,
            is_virtual_payment=True,
        )
        real = Payment.objects.create(
            user=self.user, amount=Decimal("3"), invoice=invoice
        )
        return invoice, virtual, real

    def test_instance_delete_removes_virtual_keeps_real(self):
        invoice, virtual, real = self._make_invoice_with_payments()
        invoice.delete()
        self.assertFalse(Payment.objects.filter(pk=virtual.pk).exists())
        real.refresh_from_db()
        self.assertIsNone(real.invoice_id)  # un-billed via SET_NULL

    def test_queryset_delete_removes_virtual(self):
        invoice, virtual, real = self._make_invoice_with_payments()
        Invoice.objects.filter(pk=invoice.pk).delete()
        self.assertFalse(Payment.objects.filter(pk=virtual.pk).exists())
        self.assertTrue(Payment.objects.filter(pk=real.pk).exists())


class EasyVereinInvoiceCreationTest(TestCase):
    """_ev_create_invoice_for_user: what pybarsys settles must equal what EV is told.

    The EasyVerein API is mocked out; everything on the pybarsys side is real.
    """

    def setUp(self):
        self.payer = User.objects.create_user("payer@example.com", "Payer", "pw")
        self.payer.easyverein_contact_details_url = "https://ev.example/contact/1"
        self.payer.save()
        cat = Category.objects.create(name="Drinks")
        # 1.00 per unit, so quantity == euros
        self.prod = Product.objects.create(
            category=cat, name="Cola", price="1.00", amount="0.5 l"
        )

    def buy(self, user, quantity):
        Purchase.objects.create_from_product(self.prod, user=user, quantity=quantity)

    def run_ev_invoice(self, create_with_items=None):
        """Run the real function against a fake EasyVerein API.

        Returns (result, sent) where `sent` collects the arguments the EasyVerein
        client was called with.
        """
        sent = {}

        def default_create(invoice_create, items, set_draft_state=None):
            sent["invoice"] = invoice_create
            sent["items"] = items
            return SimpleNamespace(id=4711)

        deleted = []
        fake_api = SimpleNamespace(
            invoice=SimpleNamespace(
                create_with_items=create_with_items or default_create,
                delete=deleted.append,
            )
        )
        sent["deleted"] = deleted
        conn = view_helpers.EmailConnectionWrapper(fake_sending_mails=True)
        with mock.patch.object(views, "_get_ev_api", return_value=fake_api):
            result = views._ev_create_invoice_for_user(self.payer, "", conn)
        return result, sent

    def test_settlement_equals_ev_total_including_dependants(self):
        dependant = User.objects.create_user("dep@example.com", "Dep", "pw")
        dependant.purchases_paid_by_other = self.payer
        dependant.save()

        self.buy(self.payer, 20)
        Invoice.objects.create_for_user(self.payer)  # carried balance of -20
        self.buy(self.payer, 5)
        self.buy(dependant, 7)
        Payment.objects.create(
            user=self.payer,
            amount=Decimal("3.00"),
            payment_method=Payment.PAYMENT_METHOD_BANK,
        )

        result, sent = self.run_ev_invoice()

        # 20 carried + 5 own + 7 dependant - 3 deposited
        expected = Decimal("29.00")
        self.assertTrue(result["ok"], result["detail"])
        self.assertEqual(self.payer.account_balance(), Decimal("0"))

        virtual = Payment.objects.get(is_virtual_payment=True)
        self.assertEqual(virtual.amount, expected)
        self.assertEqual(sent["invoice"].kind, "revenue")
        self.assertEqual(Decimal(str(sent["invoice"].totalPrice)), expected)
        # the line items must add up to the same number
        self.assertEqual(
            sum(Decimal(str(i.totalPrice)) for i in sent["items"]), expected
        )
        self.assertTrue(any("Dep" in i.title for i in sent["items"]))

    def test_credit_balance_is_sent_as_a_positive_credit_invoice(self):
        self.buy(self.payer, 10)
        Payment.objects.create(
            user=self.payer,
            amount=Decimal("30.00"),
            payment_method=Payment.PAYMENT_METHOD_BANK,
        )

        result, sent = self.run_ev_invoice()

        self.assertTrue(result["ok"], result["detail"])
        self.assertEqual(self.payer.account_balance(), Decimal("0"))
        # pybarsys owes the user 20, so the settlement payment is negative ...
        self.assertEqual(Payment.objects.get(is_virtual_payment=True).amount, -20)
        # ... while EasyVerein gets a credit invoice with a positive total
        self.assertEqual(sent["invoice"].kind, "credit")
        self.assertEqual(Decimal(str(sent["invoice"].totalPrice)), Decimal("20.00"))

    def test_pending_marker_is_replaced_once_easyverein_confirms(self):
        Purchase.objects.create_from_product(self.prod, user=self.payer, quantity=20)

        _result, _sent = self.run_ev_invoice()

        invoice = Invoice.objects.get()
        self.assertNotEqual(invoice.comment, views.EV_PUSH_PENDING_COMMENT)
        self.assertIn("4711", invoice.comment)

    def test_interrupted_push_leaves_a_findable_orphan(self):
        """The pybarsys side commits before the API call, so a crash in between
        zeroes a balance without EasyVerein ever hearing about it."""
        Purchase.objects.create_from_product(self.prod, user=self.payer, quantity=20)

        # A killed thread does not run the except block either, so raise something
        # `except Exception` cannot catch - that is what makes the orphan survive.
        class Killed(BaseException):
            pass

        def killed_mid_call(invoice_create, items, set_draft_state=None):
            raise Killed()

        with self.assertRaises(Killed):
            self.run_ev_invoice(create_with_items=killed_mid_call)

        orphan = Invoice.objects.get()
        self.assertEqual(orphan.comment, views.EV_PUSH_PENDING_COMMENT)
        self.assertEqual(self.payer.account_balance(), Decimal("0"))

    def test_easyverein_failure_rolls_back_the_pybarsys_side(self):
        self.buy(self.payer, 20)
        Invoice.objects.create_for_user(self.payer)

        def boom(invoice_create, items, set_draft_state=None):
            raise RuntimeError("EasyVerein is down")

        result, _sent = self.run_ev_invoice(create_with_items=boom)

        self.assertFalse(result["ok"])
        self.assertIn("rolled back", result["detail"])
        self.assertFalse(Payment.objects.filter(is_virtual_payment=True).exists())
        self.assertEqual(Invoice.objects.count(), 1)  # only the carried-balance one
        self.assertEqual(self.payer.account_balance(), Decimal("-20.00"))


class EasyVereinInvoiceJobGuardTest(TestCase):
    """A second job over the same user would bill them twice in EasyVerein."""

    def setUp(self):
        self.user = User.objects.create_user("u@example.com", "U", "pw")
        views._ev_invoice_jobs.clear()

    def tearDown(self):
        views._ev_invoice_jobs.clear()

    def start(self, user_ids):
        """Register a job without actually running it."""
        with mock.patch.object(views.threading, "Thread"):
            return views._ev_invoice_start_job(user_ids, comment="")

    def test_same_user_is_refused_while_a_job_is_running(self):
        self.start([self.user.pk])

        with self.assertRaises(ValueError) as caught:
            self.start([self.user.pk])

        self.assertIn("U", str(caught.exception))

    def test_other_users_are_unaffected(self):
        other = User.objects.create_user("o@example.com", "O", "pw")
        self.start([self.user.pk])

        self.assertTrue(self.start([other.pk]))

    def test_finished_jobs_do_not_block(self):
        job_id = self.start([self.user.pk])
        views._ev_invoice_jobs[job_id]["status"] = "finished"

        self.assertTrue(self.start([self.user.pk]))


class SiteSettingsFormFieldGatingTest(SimpleTestCase):
    """The form exposes EasyVerein fields only when the integration is active."""

    @ev_active
    def test_easyverein_fields_shown_when_active(self):
        fields = SiteSettingsForm().fields
        self.assertTrue(any(name.startswith("easyverein_") for name in fields))

    @ev_inactive
    def test_no_easyverein_fields_when_inactive(self):
        fields = SiteSettingsForm().fields
        self.assertFalse(any(name.startswith("easyverein_") for name in fields))
