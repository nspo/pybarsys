from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase
from easyverein.models import ContactDetails

from barsys.forms import SiteSettingsForm
from barsys.models import Invoice, Payment, User
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
