import csv
import re
import os.path
import threading
import uuid

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core import exceptions, paginator
from django.db import connection
from django.db.models import Q
from django.http import (
    HttpResponseRedirect,
    HttpResponseForbidden,
    HttpResponse,
    HttpRequest,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils.text import Truncator
from django.views.generic import edit, View, TemplateView
from django.views.generic.detail import DetailView
from django_filters.views import FilterView
from easyverein import EasyvereinAPI
from easyverein.models import (
    ContactDetails,
    ContactDetailsFilter,
    InvoiceCreate,
    InvoiceItemCreate,
)
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from barsys.serializers import PurchaseSerializer, UserSerializer, ProductSerializer
from pybarsys.settings import PybarsysPreferences
from . import filters
from . import view_helpers
from .forms import *
from .models import SiteSettings
from .templatetags.barsys_helpers import currency
from .view_helpers import (
    get_renderable_stats_elements,
    get_most_bought_product_for_user,
    get_most_bought_product_for_users,
)


class UserIsAdminMixin(UserPassesTestMixin):
    raise_exception = False
    permission_denied_message = "User is not an admin"
    login_url = "user_login"

    def test_func(self):
        u = self.request.user
        if u.is_authenticated:
            # against redirect loops
            self.raise_exception = True

        return u.is_active and u.is_staff

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        context["pybarsys_preferences"] = PybarsysPreferences
        return context


class UserListView(UserIsAdminMixin, FilterView):
    filterset_class = filters.UserFilter
    template_name = "barsys/admin/user_list.html"

    paginate_by = 10


class UserExportView(UserIsAdminMixin, FilterView):
    filterset_class = filters.UserFilter

    def render_to_response(self, context, **response_kwargs):
        # Could use timezone.now(), but that makes the string much longer
        filename = "{}-pybarsys-users-export.csv".format(
            datetime.datetime.now().replace(microsecond=0).isoformat()
        )

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="{}"'.format(filename)

        writer = csv.writer(response)
        writer.writerow(
            [
                "display_name",
                "email",
                "pays_themselves",
                "account_balance",
                "unbilled_purchases",
                "unbilled_payments",
            ]
        )

        for user in self.object_list:
            writer.writerow(
                [
                    user.display_name,
                    user.email,
                    user.pays_themselves(),
                    user.account_balance(),
                    user.purchases().unbilled().sum_cost(),
                    user.payments().unbilled().sum_amount(),
                ]
            )

        return response


class UserDetailView(UserIsAdminMixin, DetailView):
    model = User
    template_name = "barsys/admin/user_detail.html"
    purchases_paginate_by = 5
    payments_paginate_by = 5
    invoices_paginate_by = 5

    def get_context_data(self, **kwargs):
        context = super(UserDetailView, self).get_context_data(**kwargs)

        purchases = self.object.purchases()

        purchases_page = self.request.GET.get("purchases_page")
        purchases_paginator = paginator.Paginator(purchases, self.purchases_paginate_by)
        # Catch invalid page numbers
        try:
            purchases_page_obj = purchases_paginator.page(purchases_page)
        except (paginator.PageNotAnInteger, paginator.EmptyPage):
            purchases_page_obj = purchases_paginator.page(1)

        context["purchases_page_obj"] = purchases_page_obj

        payments = self.object.payments()

        payments_page = self.request.GET.get("payments_page")
        payments_paginator = paginator.Paginator(payments, self.payments_paginate_by)
        try:
            payments_page_obj = payments_paginator.page(payments_page)
        except (paginator.PageNotAnInteger, paginator.EmptyPage):
            payments_page_obj = payments_paginator.page(1)

        context["payments_page_obj"] = payments_page_obj

        invoices = self.object.invoices()

        invoices_page = self.request.GET.get("invoices_page")
        invoices_paginator = paginator.Paginator(invoices, self.invoices_paginate_by)
        try:
            invoices_page_obj = invoices_paginator.page(invoices_page)
        except (paginator.PageNotAnInteger, paginator.EmptyPage):
            invoices_page_obj = invoices_paginator.page(1)

        context["invoices_page_obj"] = invoices_page_obj

        return context


class EasyVereinContactFetchMixin:
    """Adds a "fetch_ev_contacts" POST action to a user create/update view.

    The action re-renders the form (unbound, pre-filled from POST so no premature
    validation errors) together with ranked, still-unattached EasyVerein contact
    suggestions for the entered display name. Concrete views set ``self.object``
    before delegating to :meth:`ev_contact_fetch_response`.
    """

    def _fetch_unattached_contacts(self) -> list[ContactDetails]:
        """Non-company EV contacts not linked to any *other* pybarsys user.

        The edited user's own contact (if any) stays selectable.
        """
        ev = _get_ev_api()
        contacts = ev.contact_details.get_all(
            search=ContactDetailsFilter(deleted=False), limit_per_page=100
        )
        contacts = [c for c in contacts if not c.isCompany]
        other_users = User.objects.attached_to_easyverein()
        if self.object is not None:
            other_users = other_users.exclude(pk=self.object.pk)
        assigned_urls = set(
            other_users.values_list("easyverein_contact_details_url", flat=True)
        )
        return [c for c in contacts if _ev_contact_url(c.id) not in assigned_urls]

    def ev_contact_fetch_response(self, request: HttpRequest) -> HttpResponse:
        # Render the form unbound (pre-filled from POST) so this lookup action does not
        # surface validation errors. Unchecked checkboxes are absent from POST, so
        # normalize boolean fields to their submitted presence to preserve their state.
        initial = request.POST.dict()
        for name, field in self.form_class.base_fields.items():
            if isinstance(field, forms.BooleanField):
                initial[name] = name in request.POST
        form = self.form_class(instance=self.object, initial=initial)
        context = self.get_context_data(form=form)
        try:
            context["ev_contacts"] = _ev_rank_contacts_for_name(
                self._fetch_unattached_contacts(), request.POST.get("display_name", "")
            )
        except Exception as e:
            messages.error(
                request, "Error fetching contacts from EasyVerein: {}".format(e)
            )
        return self.render_to_response(context)


class UserCreateView(EasyVereinContactFetchMixin, UserIsAdminMixin, edit.CreateView):
    model = User
    form_class = UserCreateForm
    template_name = "barsys/admin/user_new.html"

    def post(self, request, *args, **kwargs):
        if request.POST.get("action") == "fetch_ev_contacts":
            self.object = None
            return self.ev_contact_fetch_response(request)
        return super().post(request, *args, **kwargs)


class UserUpdateView(EasyVereinContactFetchMixin, UserIsAdminMixin, edit.UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = "barsys/admin/user_update.html"

    def post(self, request, *args, **kwargs):
        if request.POST.get("action") == "fetch_ev_contacts":
            self.object = self.get_object()
            return self.ev_contact_fetch_response(request)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        # Non-blocking warning: the create form forbids this state, update only warns.
        user = self.object
        if (
            PybarsysPreferences.EasyVerein.ACTIVE
            and user.is_buyer
            and user.purchases_paid_by_other_id is None
            and not user.easyverein_contact_details_url
        ):
            messages.error(
                self.request,
                "You should attach this user to EasyVerein! "
                "This buyer pays for themselves but is not attached to an EasyVerein "
                "contact, which will lead to non-invoiceable purchases.",
            )
        return response


class CheckedDeleteView(View):
    """Base view class for calling a check on object.cannot_be_deleted() before .delete()ing it"""

    success_url = None
    cancel_url = None
    template_name = "barsys/admin/confirm_delete.html"
    model = None
    object = None

    def delete(self, request, pk):
        self.object = get_object_or_404(self.model, pk=pk)
        success_url = self.get_success_url()
        cannot_be_deleted = self.object.cannot_be_deleted()
        if cannot_be_deleted:
            return HttpResponseForbidden(cannot_be_deleted)
        else:
            self.object.delete()
            return HttpResponseRedirect(success_url)

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)

    def get_success_url(self):
        if self.success_url:
            return self.success_url.format(**self.object.__dict__)
        else:
            raise exceptions.ImproperlyConfigured(
                "No URL to redirect to. Provide a success_url."
            )

    def get_extra_notices(self) -> list[str]:
        return []

    def get(self, request, pk):
        self.object = get_object_or_404(self.model, pk=pk)
        context = {
            "object": self.object,
            "cannot_be_deleted": self.object.cannot_be_deleted(),
            "cancel_url": self.cancel_url,
            "pybarsys_preferences": PybarsysPreferences,
            "extra_notices": self.get_extra_notices(),
        }
        return render(request, self.template_name, context)


class UserDeleteView(UserIsAdminMixin, CheckedDeleteView):
    success_url = reverse_lazy("admin_user_list")
    model = User


class PurchaseListView(UserIsAdminMixin, FilterView):
    filterset_class = filters.PurchaseFilter
    template_name = "barsys/admin/purchase_list.html"
    paginate_by = 10


class PurchaseDetailView(UserIsAdminMixin, DetailView):
    model = Purchase
    template_name = "barsys/admin/purchase_detail.html"


class PurchaseCreateView(UserIsAdminMixin, edit.CreateView):
    model = Purchase
    form_class = PurchaseForm
    template_name = "barsys/admin/purchase_new.html"


class PurchaseUpdateView(UserIsAdminMixin, edit.UpdateView):
    model = Purchase
    form_class = PurchaseForm
    template_name = "barsys/admin/purchase_update.html"

    def get(self, request, *args, **kwargs):
        if self.get_object().has_invoice():
            return self.handle_with_invoice(request)
        return super(PurchaseUpdateView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self.get_object().has_invoice():
            return self.handle_with_invoice(request)
        return super(PurchaseUpdateView, self).post(request, *args, **kwargs)

    def handle_with_invoice(self, request):
        messages.error(request, "Cannot update this purchase because it has an invoice")
        return redirect("admin_purchase_list")


class PurchaseDeleteView(UserIsAdminMixin, CheckedDeleteView):
    model = Purchase
    success_url = reverse_lazy("admin_purchase_list")


# Category


class CategoryListView(UserIsAdminMixin, FilterView):
    filterset_class = filters.CategoryFilter
    template_name = "barsys/admin/category_list.html"

    paginate_by = 10


class CategoryDetailView(UserIsAdminMixin, DetailView):
    model = Category
    template_name = "barsys/admin/category_detail.html"


class CategoryCreateView(UserIsAdminMixin, edit.CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "barsys/admin/category_new.html"


class CategoryUpdateView(UserIsAdminMixin, edit.UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "barsys/admin/category_update.html"


class CategoryDeleteView(UserIsAdminMixin, CheckedDeleteView):
    model = Category
    success_url = reverse_lazy("admin_category_list")


# Category END
# Product BEGIN


class ProductListView(UserIsAdminMixin, FilterView):
    filterset_class = filters.ProductFilter
    template_name = "barsys/admin/product_list.html"

    paginate_by = 10


class ProductDetailView(UserIsAdminMixin, DetailView):
    model = Product
    template_name = "barsys/admin/product_detail.html"


class ProductCreateView(UserIsAdminMixin, edit.CreateView):
    model = Product
    form_class = ProductForm
    template_name = "barsys/admin/product_new.html"


class ProductUpdateView(UserIsAdminMixin, edit.UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "barsys/admin/product_update.html"


class ProductDeleteView(UserIsAdminMixin, CheckedDeleteView):
    model = Product
    success_url = reverse_lazy("admin_product_list")


# Product END
# StatsDisplay BEGIN


class StatsDisplayListView(UserIsAdminMixin, FilterView):
    filterset_class = filters.StatsDisplayFilter
    template_name = "barsys/admin/statsdisplay_list.html"

    paginate_by = 10


class StatsDisplayDetailView(UserIsAdminMixin, DetailView):
    model = StatsDisplay
    template_name = "barsys/admin/statsdisplay_detail.html"


class StatsDisplayCreateView(UserIsAdminMixin, edit.CreateView):
    model = StatsDisplay
    form_class = StatsDisplayForm
    template_name = "barsys/admin/statsdisplay_new.html"


class StatsDisplayUpdateView(UserIsAdminMixin, edit.UpdateView):
    model = StatsDisplay
    form_class = StatsDisplayForm
    template_name = "barsys/admin/statsdisplay_update.html"


class StatsDisplayDeleteView(UserIsAdminMixin, CheckedDeleteView):
    model = StatsDisplay
    success_url = reverse_lazy("admin_statsdisplay_list")


# StatsDisplay END
# Payment BEGIN


class PaymentListView(UserIsAdminMixin, FilterView):
    filterset_class = filters.PaymentFilter
    template_name = "barsys/admin/payment_list.html"
    paginate_by = 10


class PaymentExportView(UserIsAdminMixin, FilterView):
    filterset_class = filters.PaymentFilter

    def render_to_response(self, context, **response_kwargs):
        # Could use timezone.now(), but that makes the string much longer
        filename = "{}-pybarsys-payments-export.csv".format(
            datetime.datetime.now().replace(microsecond=0).isoformat()
        )

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="{}"'.format(filename)

        writer = csv.writer(response)
        writer.writerow(
            [
                "created",
                "value_date",
                "email",
                "display_name",
                "amount",
                "payment_method",
                "comment",
            ]
        )

        for obj in self.object_list:
            writer.writerow(
                [
                    obj.created_date,
                    obj.value_date,
                    obj.user.email,
                    obj.user.display_name,
                    obj.amount,
                    obj.get_payment_method_display(),
                    obj.comment,
                ]
            )

        return response


class PaymentDetailView(UserIsAdminMixin, DetailView):
    model = Payment
    template_name = "barsys/admin/payment_detail.html"


class PaymentCreateView(UserIsAdminMixin, edit.CreateView):
    model = Payment
    form_class = PaymentForm
    template_name = "barsys/admin/payment_new.html"

    def form_valid(self, form):
        user = form.cleaned_data["user"]
        if not user.pays_themselves():
            messages.error(
                self.request,
                "Cannot add payment for {}: purchases are paid by {}.".format(
                    user, user.purchases_paid_by_other
                ),
            )
            return redirect("admin_payment_new")
        return super().form_valid(form)


class PaymentUpdateView(UserIsAdminMixin, edit.UpdateView):
    model = Payment
    form_class = PaymentForm
    template_name = "barsys/admin/payment_update.html"

    def get(self, request, *args, **kwargs):
        if self.get_object().has_invoice():
            return self.handle_with_invoice(request)
        return super(PaymentUpdateView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self.get_object().has_invoice():
            return self.handle_with_invoice(request)
        return super(PaymentUpdateView, self).post(request, *args, **kwargs)

    def handle_with_invoice(self, request):
        messages.error(request, "Cannot update this purchase because it has an invoice")
        return redirect("admin_payment_list")


class PaymentDeleteView(UserIsAdminMixin, CheckedDeleteView):
    model = Payment
    success_url = reverse_lazy("admin_payment_list")


# PAYMENT END
# Invoice BEGIN


class InvoiceListView(UserIsAdminMixin, FilterView):
    filterset_class = filters.InvoiceFilter
    template_name = "barsys/admin/invoice_list.html"
    paginate_by = 10


class InvoiceDetailView(UserIsAdminMixin, DetailView):
    model = Invoice
    template_name = "barsys/admin/invoice_detail.html"

    def get_context_data(self, **kwargs):
        context = super(InvoiceDetailView, self).get_context_data(**kwargs)

        context["own_purchases"] = self.object.own_purchases()
        context["other_purchases_grouped"] = self.object.other_purchases_grouped()

        return context


class InvoiceResendView(UserIsAdminMixin, View):
    def get(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        try:
            conn = view_helpers.EmailConnectionWrapper(fake_sending_mails=False)
        except Exception as e:
            messages.error(request, "Could not connect to mail server: {}".format(e))
            return redirect("admin_invoice_list")
        if conn.send_message(view_helpers.generate_email_invoice(invoice)):
            messages.success(request, "Invoice mail resent successfully.")
        else:
            messages.error(
                request, "Failed to resend invoice mail: {}".format(conn.last_error)
            )
        conn.close()
        return redirect("admin_invoice_list")


class PaymentReminderSendView(UserIsAdminMixin, View):
    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user.account_balance() >= 0:
            messages.warning(
                request,
                "Payment reminder not sent: {}'s account balance is not below 0.".format(
                    user
                ),
            )
            return redirect("admin_user_detail", pk=pk)
        try:
            conn = view_helpers.EmailConnectionWrapper(fake_sending_mails=False)
        except Exception as e:
            messages.error(request, "Could not connect to mail server: {}".format(e))
            return redirect("admin_user_detail", pk=pk)
        if conn.send_message(view_helpers.generate_email_payment_reminder(user)):
            messages.success(request, "Payment reminder sent successfully.")
        else:
            messages.error(
                request, "Failed to send payment reminder: {}".format(conn.last_error)
            )
        conn.close()
        return redirect("admin_user_detail", pk=pk)


# for debugging mail


class InvoiceMailDebugView(UserIsAdminMixin, DetailView):
    model = Invoice
    template_name = os.path.join(
        PybarsysPreferences.EMAIL.TEMPLATE_DIR, "normal_invoice.html.html"
    )

    def get_context_data(self, **kwargs):
        context = super(InvoiceMailDebugView, self).get_context_data(**kwargs)

        invoice = self.object

        context["invoice"] = invoice
        context["recipient"] = invoice.recipient
        context["pybarsys_preferences"] = PybarsysPreferences
        context["subject"] = PybarsysPreferences.EMAIL.INVOICE_SUBJECT
        context["own_purchases"] = invoice.own_purchases()
        context["other_purchases_grouped"] = invoice.other_purchases_grouped()
        context["last_invoices"] = invoice.recipient.invoices()[:5]
        context["payments"] = invoice.payments()

        return context


class PaymentReminderMailDebugView(UserIsAdminMixin, DetailView):
    model = User
    template_name = os.path.join(
        PybarsysPreferences.EMAIL.TEMPLATE_DIR, "payment_reminder.html.html"
    )

    def get_context_data(self, **kwargs):
        context = super(PaymentReminderMailDebugView, self).get_context_data(**kwargs)

        user = self.object

        context["recipient"] = user
        context["pybarsys_preferences"] = PybarsysPreferences
        context["subject"] = PybarsysPreferences.EMAIL.PAYMENT_REMINDER_SUBJECT
        context["last_invoices"] = user.invoices()[:5]
        context["last_payments"] = user.payments()[:5]

        return context


# end debugging mail


class InvoiceCreateView(UserIsAdminMixin, edit.FormView):
    template_name = "barsys/admin/invoice_new.html"
    form_class = InvoicesCreateForm
    success_url = reverse_lazy("admin_invoice_list")

    def dispatch(self, request, *args, **kwargs):
        if PybarsysPreferences.EasyVerein.ACTIVE:
            url = reverse("admin_easyverein_invoice_new")
            user_pk = request.GET.get("user") or request.POST.get("user")
            if user_pk:
                url += "?user={}".format(user_pk)
            return redirect(url)
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        user_pk = self.request.GET.get("user")
        if user_pk:
            initial["users"] = [user_pk]
        return initial

    def form_valid(self, form):
        view_helpers.create_invoices(
            self.request,
            users=form.cleaned_data["users"],
            send_mails=form.cleaned_data["send_invoices"],
            send_dependant_notifications=form.cleaned_data[
                "send_dependant_notifications"
            ],
            send_payment_reminders=form.cleaned_data["send_payment_reminders"],
            autolock_accounts=form.cleaned_data["autolock_accounts"],
            comment=form.cleaned_data["comment"],
        )
        return super(InvoiceCreateView, self).form_valid(form)


class InvoiceDeleteView(UserIsAdminMixin, CheckedDeleteView):
    model = Invoice
    success_url = reverse_lazy("admin_invoice_list")

    def get_extra_notices(self) -> list[str]:
        virtual = self.object.payments().filter(is_virtual_payment=True)
        if virtual.exists():
            return [
                "This will also delete the associated virtual payment of {}.".format(
                    currency(virtual.sum_amount())
                ),
                "You must delete the automatically created EasyVerein invoice manually: {}".format(
                    self.object.comment
                ),
            ]
        return []


# Invoice END
# Statistics BEGIN


class PurchaseStatisticsByCategoryView(UserIsAdminMixin, FilterView):
    filterset_class = filters.PurchaseFilter
    template_name = "barsys/admin/purchase_statistics.html"
    paginate_by = 10

    metrics = {
        "num_purchases": models.Count("id"),
        "average_cost": models.Avg(
            F("quantity") * F("product_price"),
            output_field=DecimalField(decimal_places=2),
        ),
        "average_quantity": models.Avg(
            F("quantity"), output_field=DecimalField(decimal_places=2)
        ),
        "total_quantity": models.Sum(F("quantity")),
        "total_sales": models.Sum(
            F("quantity") * F("product_price"),
            output_field=DecimalField(decimal_places=2),
        ),
    }

    def get_context_data(self, **kwargs):
        context = super(PurchaseStatisticsByCategoryView, self).get_context_data(
            **kwargs
        )

        context["title"] = "Purchase statistics grouped by category"
        context["grouped_by"] = ["product_category"]
        context["grouped_by_title"] = ["Category"]

        context["summary"] = list(
            context["filter"]
            .qs.values("product_category")
            .annotate(**self.metrics)
            .order_by("-total_sales")
        )

        context["summary_total"] = dict(context["filter"].qs.aggregate(**self.metrics))

        return context

    def get_filterset_kwargs(self, filterset_class):
        kwargs = super(PurchaseStatisticsByCategoryView, self).get_filterset_kwargs(
            filterset_class
        )
        if kwargs["data"] is None:
            kwargs["data"] = {"is_free_item_purchase": False}
        elif "is_free_item_purchase" not in kwargs["data"]:
            kwargs["data"] = kwargs["data"].copy()
            kwargs["data"]["is_free_item_purchase"] = False

        return kwargs


class PurchaseStatisticsByProductView(UserIsAdminMixin, FilterView):
    filterset_class = filters.PurchaseFilter
    template_name = "barsys/admin/purchase_statistics.html"
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super(PurchaseStatisticsByProductView, self).get_context_data(
            **kwargs
        )

        context["title"] = "Purchase statistics grouped by product"
        context["grouped_by"] = ["product_name", "product_amount"]
        context["grouped_by_title"] = ["Product", "Amount"]

        context["summary"] = list(
            context["filter"]
            .qs.values("product_name", "product_amount")
            .annotate(**PurchaseStatisticsByCategoryView.metrics)
            .order_by("-total_sales")
        )

        context["summary_total"] = dict(
            context["filter"].qs.aggregate(**PurchaseStatisticsByCategoryView.metrics)
        )

        return context

    def get_filterset_kwargs(self, filterset_class):
        kwargs = super(PurchaseStatisticsByProductView, self).get_filterset_kwargs(
            filterset_class
        )
        if kwargs["data"] is None:
            kwargs["data"] = {"is_free_item_purchase": False}
        elif "is_free_item_purchase" not in kwargs["data"]:
            kwargs["data"] = kwargs["data"].copy()
            kwargs["data"]["is_free_item_purchase"] = False

        return kwargs


class PurchaseStatisticsByUserView(UserIsAdminMixin, FilterView):
    filterset_class = filters.PurchaseFilter
    template_name = "barsys/admin/purchase_statistics.html"
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super(PurchaseStatisticsByUserView, self).get_context_data(**kwargs)

        context["title"] = "Purchase statistics grouped by user"
        context["grouped_by"] = ["user__display_name"]
        context["grouped_by_title"] = ["User"]

        context["summary"] = list(
            context["filter"]
            .qs.values("user", "user__display_name")
            .annotate(**PurchaseStatisticsByCategoryView.metrics)
            .order_by("-total_sales")
        )

        context["summary_total"] = dict(
            context["filter"].qs.aggregate(**PurchaseStatisticsByCategoryView.metrics)
        )

        return context

    def get_filterset_kwargs(self, filterset_class):
        kwargs = super(PurchaseStatisticsByUserView, self).get_filterset_kwargs(
            filterset_class
        )
        if kwargs["data"] is None:
            kwargs["data"] = {"is_free_item_purchase": False}
        elif "is_free_item_purchase" not in kwargs["data"]:
            kwargs["data"] = kwargs["data"].copy()
            kwargs["data"]["is_free_item_purchase"] = False

        return kwargs


class UserStatisticsByAccountBalance(FilterView):
    filterset_class = filters.UserFilter
    template_name = "barsys/admin/user_account_balance_statistics.html"
    # The displayed rows are the separately-computed `balances` aggregation, not the
    # FilterView's object_list, so it is paginated manually in get_context_data.
    page_size = 20

    def get_context_data(self, **kwargs):
        context = super(UserStatisticsByAccountBalance, self).get_context_data(**kwargs)

        invoices = Invoice.objects.filter(recipient_id__in=context["filter"].qs)
        balances = (
            invoices.values("recipient_id", "recipient__display_name")
            .order_by("recipient_id")
            .annotate(
                account_balance=models.Sum(F("amount_payments") - F("amount_purchases"))
            )
            .order_by("account_balance")
        )

        page = paginator.Paginator(balances, self.page_size).get_page(
            self.request.GET.get("page")
        )
        context["balances"] = page
        context["paginator"] = page.paginator
        context["page_obj"] = page
        context["is_paginated"] = page.has_other_pages()
        return context


# Statistics END
# ProductAutochangeSet BEGIN


class ProductAutochangeSetListView(UserIsAdminMixin, FilterView):
    filterset_class = filters.ProductAutochangeSetFilter
    template_name = "barsys/admin/productautochangeset_list.html"
    paginate_by = 10


class ProductAutochangeSetManageView(UserIsAdminMixin, View):
    template_name = "barsys/admin/productautochangeset_form.html"
    new_title = "New Product Autochange Set"
    update_title = "Update Product Autochange Set"

    def post(self, request, pk=None):
        if pk is None:
            context = {"title": self.new_title}
            pcs = ProductAutochangeSet()
        else:
            context = {"title": self.update_title}
            pcs = get_object_or_404(ProductAutochangeSet, pk=pk)

        formset = ProductAutochangeInlineFormSet(
            request.POST, request.FILES, instance=pcs, prefix="nested"
        )
        form = ProductAutochangeSetForm(
            request.POST, request.FILES, instance=pcs, prefix="main"
        )

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.info(request, "Successfully saved {}".format(pcs))
            return redirect("admin_productautochangeset_update", pk=pcs.pk)

        context["form"] = form
        context["formset"] = formset
        return render(request, self.template_name, context)

    def get(self, request, pk=None):
        if pk is None:
            context = {"title": self.new_title}
            pcs = ProductAutochangeSet()
        else:
            context = {"title": self.update_title}
            pcs = get_object_or_404(ProductAutochangeSet, pk=pk)

        formset = ProductAutochangeInlineFormSet(instance=pcs, prefix="nested")
        form = ProductAutochangeSetForm(instance=pcs, prefix="main")

        context["form"] = form
        context["formset"] = formset
        return render(request, self.template_name, context)


class ProductAutochangeSetDeleteView(UserIsAdminMixin, CheckedDeleteView):
    model = ProductAutochangeSet
    success_url = reverse_lazy("admin_productautochangeset_list")


class ProductAutochangeSetExecuteView(UserIsAdminMixin, View):
    def get(self, request, pk):
        pacs = get_object_or_404(ProductAutochangeSet, pk=pk)

        pacs.execute()

        messages.info(
            request, "Successfully executed product autochange set: {}".format(pacs)
        )
        return redirect("admin_productautochangeset_list")


class ProductAutochangeSetImportView(UserIsAdminMixin, View):
    def get(self, request, pk):
        pacs = get_object_or_404(ProductAutochangeSet, pk=pk)

        pacs.import_current_state()

        messages.info(
            request, "Successfully imported current state into {}".format(pacs)
        )
        return redirect("admin_productautochangeset_update", pacs.pk)


# ProductAutochangeSet END


# FreeItem BEGIN


class FreeItemListView(UserIsAdminMixin, FilterView):
    filterset_class = filters.FreeItemFilter
    template_name = "barsys/admin/freeitem_list.html"
    paginate_by = 10


class FreeItemCreateView(UserIsAdminMixin, edit.CreateView):
    model = FreeItem
    form_class = FreeItemForm
    template_name = "barsys/admin/generic_form.html"

    def get_context_data(self, **kwargs):
        context = super(FreeItemCreateView, self).get_context_data(**kwargs)
        context["title"] = "New free item"
        return context


class FreeItemUpdateView(UserIsAdminMixin, edit.UpdateView):
    model = FreeItem
    form_class = FreeItemForm
    template_name = "barsys/admin/generic_form.html"

    def get_context_data(self, **kwargs):
        context = super(FreeItemUpdateView, self).get_context_data(**kwargs)
        context["title"] = "Update free item"
        return context


class FreeItemDeleteView(UserIsAdminMixin, CheckedDeleteView):
    model = FreeItem
    success_url = reverse_lazy("admin_freeitem_list")


# FreeItem END


# admin area end


class MainUserPurchaseView(View):
    def post(self, request, user_id):
        form = SingleUserSinglePurchaseForm(request.POST)

        if form.is_valid():
            if not form.is_free_item_purchase:
                result = purchase_no_free_item(form)
                product = Product.objects.get(pk=form.cleaned_data["product_id"])

                if "free_item" in result:
                    messages.info(
                        request,
                        "Yay! You successfully purchased {}x {} for others! "
                        "Anyone may now buy that for free until there's none left.".format(
                            result["free_item"].leftover_quantity, product.name
                        ),
                    )
            else:
                # free item purchase
                result = purchase_free_item(form)

            if form.cleaned_data["purchase_more_for_same_users"]:
                # notify user of successful purchase, so they are not confused b/c they
                # stay on the same page
                messages.info(
                    request, "Purchase successful: {}".format(result["purchase"])
                )

                return redirect("main_user_purchase", user_id)
            else:
                return redirect("main_user_list")
        else:
            messages.error(request, form.errors)
            return redirect("main_user_purchase", user_id)

    def get(self, request, user_id):
        user = get_object_or_404(User.objects.active().buyers(), pk=user_id)

        if user.is_autolocked:
            messages.error(request, "User is currently autolocked: {}".format(user))
            return redirect("main_user_list")
        if not user.pays_themselves() and user.purchases_paid_by_other.is_autolocked:
            messages.error(
                request,
                "The payer of this users' purchases is currently autolocked: {}".format(
                    user
                ),
            )
            return redirect("main_user_list")

        categories = Category.objects.all()

        context = {}

        form = SingleUserSinglePurchaseForm()

        context["user"] = user
        context["categories"] = categories
        context["form"] = form
        context["free_items"] = FreeItem.objects.filter(
            purchasable=True, leftover_quantity__gte=1
        )

        context["most_bought_product"] = get_most_bought_product_for_user(user)

        return render(request, "barsys/main/user_purchase.html", context)


def purchase_no_free_item(form):
    user = User.objects.get(pk=form.cleaned_data["user_id"])
    product = Product.objects.get(pk=form.cleaned_data["product_id"])

    comment = form.cleaned_data["comment"]
    if form.cleaned_data["give_away_free"]:
        if comment:
            comment += " (give away for free)"
        else:
            comment = "give away for free"

    purchase = Purchase(
        user=user,
        product_name=product.name,
        product_amount=product.amount,
        product_category=product.category.name,
        product_price=product.price,
        quantity=form.cleaned_data["quantity"],
        comment=comment,
    )
    purchase.save()

    if form.cleaned_data["give_away_free"]:
        # create free item
        free_item = FreeItem.objects.create(
            giver=user,
            product=product,
            leftover_quantity=form.cleaned_data["quantity"],
            comment=form.cleaned_data["comment"],
            purchasable=True,
        )
        return {"purchase": purchase, "free_item": free_item}

    return {"purchase": purchase}


def purchase_free_item(form):
    user = User.objects.get(pk=form.cleaned_data["user_id"])

    # free item purchase
    free_item = FreeItem.objects.get(pk=form.cleaned_data["product_id"])
    product = free_item.product
    quantity = form.cleaned_data["quantity"]

    comment = form.cleaned_data["comment"]
    if comment:
        comment += " (free)"
    else:
        comment = "free"

    free_item.leftover_quantity -= quantity
    free_item.save()

    purchase = Purchase(
        user=user,
        product_name=product.name,
        product_amount=product.amount,
        product_category=product.category.name,
        product_price=Decimal(0),
        quantity=quantity,
        comment=comment,
        is_free_item_purchase=True,
        free_item_description=Truncator(free_item.verbose_str()).chars(120),
    )
    purchase.save()
    return {"purchase": purchase}


class MainUserListView(View):
    def get(self, request):
        all_users_ungrouped = User.objects.active().buyers().order_by("display_name")

        # Group by first letter of name
        all_users = view_helpers.group_users(all_users_ungrouped)

        jump_to_data_lines = view_helpers.get_jump_to_data_lines(all_users)

        favorite_users = User.objects.active().buyers().favorites()

        last_purchases = Purchase.objects.order_by("-created_date")[
            : PybarsysPreferences.Misc.NUM_MAIN_LAST_PURCHASES
        ]

        sidebar_stats_elements = get_renderable_stats_elements()

        context = {
            "favorites": favorite_users,
            "all_users": all_users,
            "last_purchases": last_purchases,
            "sidebar_stats_elements": sidebar_stats_elements,
            "jump_to_data_lines": jump_to_data_lines,
        }
        return render(request, "barsys/main/user_list.html", context)


class MainUserListMultiBuyView(View):
    def get(self, request):
        all_users_ungrouped = User.objects.active().buyers().order_by("display_name")

        # Group by first letter of name
        all_users = view_helpers.group_users(all_users_ungrouped)

        jump_to_data_lines = view_helpers.get_jump_to_data_lines(all_users)

        favorite_users = User.objects.active().buyers().favorites()

        last_purchases = Purchase.objects.order_by("-created_date")[
            : PybarsysPreferences.Misc.NUM_MAIN_LAST_PURCHASES
        ]

        sidebar_stats_elements = get_renderable_stats_elements()

        context = {
            "favorites": favorite_users,
            "all_users": all_users,
            "last_purchases": last_purchases,
            "sidebar_stats_elements": sidebar_stats_elements,
            "jump_to_data_lines": jump_to_data_lines,
        }
        return render(request, "barsys/main/user_list_multibuy.html", context)

    def post(self, request):
        form = MultiUserChooseForm(request.POST)
        if form.is_valid():
            pks = [str(u.pk) for u in form.cleaned_data["users"]]
            pkey_str = "/".join(pks)
            return redirect("main_user_purchase_multibuy", user_pkey_str=pkey_str)
        else:
            messages.error(request, "Invalid form data")
            return redirect("main_user_list_multibuy")


class MainUserPurchaseMultiBuyView(View):
    def get_users_qs(self, request, user_pkey_str):
        """Return queryset of users in user_pkey_str if all IDs are valid, or None otherwise"""
        try:
            user_pks = [int(n) for n in user_pkey_str.split("/")]
        except ValueError:
            messages.error(request, "Invalid format of user IDs")
            return None

        all_users = User.objects.active().buyers().filter(pk__in=user_pks)
        if all_users.count() != len(user_pks):
            # Not all users could be found
            messages.error(request, "Not all requested users are active buyers")
            return None

        users = all_users.filter(is_autolocked=False)
        if users.count() != len(user_pks):
            messages.error(
                request,
                "Some users are currently autolocked: {}".format(
                    ", ".join(
                        u.__str__() for u in all_users.exclude(is_autolocked=False)
                    )
                ),
            )
            return None

        cond_autolock2 = Q(purchases_paid_by_other=None) | Q(
            purchases_paid_by_other__is_autolocked=False
        )
        users = all_users.filter(cond_autolock2)
        if users.count() != len(user_pks):
            messages.error(
                request,
                "The payers of some users' purchases are currently autolocked: {}".format(
                    ", ".join(u.__str__() for u in all_users.exclude(cond_autolock2))
                ),
            )
            return None

        return users

    def get(self, request, user_pkey_str):
        users = self.get_users_qs(request, user_pkey_str)
        if users is None:
            return redirect("main_user_list_multibuy")

        # users is a valid queryset
        categories = Category.objects.all()

        context = {}

        form = MultiUserSinglePurchaseForm()

        context["multibuy"] = True
        context["users"] = users
        context["categories"] = categories
        context["free_items"] = FreeItem.objects.filter(
            purchasable=True, leftover_quantity__gte=1
        )
        context["form"] = form

        most_bought_product = get_most_bought_product_for_users(users)

        context["most_bought_product"] = most_bought_product

        return render(request, "barsys/main/user_purchase.html", context)

    def post(self, request, user_pkey_str):
        users = self.get_users_qs(request, user_pkey_str)
        if users is None:
            return redirect("main_user_list_multibuy")

        form = MultiUserSinglePurchaseForm(request.POST)
        form.users_qs = users

        if form.is_valid():
            if not form.is_free_item_purchase:
                product = Product.objects.get(pk=form.cleaned_data["product_id"])
                quantity = form.cleaned_data["quantity"]
                comment = form.cleaned_data["comment"]

                for user in users:
                    purchase = Purchase(
                        user=user,
                        product_name=product.name,
                        product_amount=product.amount,
                        product_category=product.category.name,
                        product_price=product.price,
                        quantity=quantity,
                        comment=comment,
                    )
                    purchase.save()
            else:
                # free item purchase
                free_item = FreeItem.objects.get(pk=form.cleaned_data["product_id"])
                product = free_item.product
                quantity_per_user = form.cleaned_data["quantity"]
                total_quantity = quantity_per_user * users.count()

                comment = form.cleaned_data["comment"]
                if comment:
                    comment += " (free)"
                else:
                    comment = "free"

                free_item.leftover_quantity -= total_quantity
                free_item.save()

                for user in users:
                    purchase = Purchase(
                        user=user,
                        product_name=product.name,
                        product_amount=product.amount,
                        product_category=product.category.name,
                        product_price=Decimal(0),
                        quantity=quantity_per_user,
                        comment=comment,
                        is_free_item_purchase=True,
                        free_item_description=Truncator(free_item.verbose_str()).chars(
                            120
                        ),
                    )
                    purchase.save()
            if form.cleaned_data["purchase_more_for_same_users"]:
                messages.info(
                    request,
                    "Successfully purchased {}x {} ({}) for the following users: {}".format(
                        purchase.quantity,
                        purchase.product_name,
                        currency(purchase.cost()),
                        ", ".join(u.display_name for u in users),
                    ),
                )

                return redirect(
                    "main_user_purchase_multibuy", user_pkey_str=user_pkey_str
                )
            else:
                return redirect("main_user_list")
        else:
            messages.error(request, form.errors)
            return redirect("main_user_purchase_multibuy", user_pkey_str=user_pkey_str)


class MainUserHistoryView(View):
    def get(self, request, user_id):
        user = get_object_or_404(User.objects.active().buyers(), pk=user_id)

        # Sum not yet billed product purchases grouped by product_category
        categories = Purchase.objects.filter(
            user_id=user_id, invoice=None
        ).stats_purchases_by_category_and_product()

        last_purchases = Purchase.objects.filter(user_id=user_id).order_by(
            "-created_date"
        )[: PybarsysPreferences.Misc.NUM_USER_PURCHASE_HISTORY]

        if user.invoices().exists():
            last_invoice = user.invoices()[0]
        else:
            last_invoice = None

        context = {
            "user": user,
            "categories": categories,
            "last_purchases": last_purchases,
            "last_invoice": last_invoice,
            "pybarsys_preferences": PybarsysPreferences,
        }
        return render(request, "barsys/main/user_history.html", context)


# EasyVerein BEGIN

EASYVEREIN_API_BASE = "https://easyverein.com/api/v2.0"
EASYVEREIN_MATCH_FIRST_NAME_CHARS = 1


def _ev_contact_url(contact_id: int) -> str:
    """URL of an EasyVerein contact-details resource (as stored on User)."""
    return "{}/contact-details/{}".format(EASYVEREIN_API_BASE, contact_id)


def _ev_clean_name(name: str) -> str:
    """Remove nickname sections from a display name (quoted, parenthetical, dash-separated)."""
    name = re.sub(r"\s*\([^)]*\)\s*", " ", name)  # (nickname)
    name = re.sub(r"\s*'[^']*'\s*", " ", name)  # 'nickname'
    name = re.sub(r'\s*"[^"]*"\s*', " ", name)  # "nickname"
    name = re.sub(r"\s*„[^“]*“\s*", " ", name)  # „nickname“ (German quotes)
    name = re.sub(r"\s*-\s*[^-]+-\s*", " ", name)  # First - Nickname - Last
    name = re.sub(r"\s*-\s*", " ", name)  # remaining dashes
    return " ".join(name.split())


def _ev_name_parts(name: str) -> tuple[str, str]:
    parts = name.split()
    if len(parts) >= 2:
        return parts[0], parts[-1]
    return (parts[0], parts[0]) if parts else ("", "")


def _ev_match_contacts(
    contacts: list[ContactDetails],
    display_name: str,
    n: int = EASYVEREIN_MATCH_FIRST_NAME_CHARS,
) -> tuple[list[ContactDetails], list[ContactDetails]]:
    """Match EV contacts against a pybarsys display name.

    Returns a (matches, same_family_name) tuple:
      - same_family_name: all contacts whose family name equals the entered last name.
      - matches: the subset of those that also match the first-name prefix (n chars,
        lengthened to n+1/n+2 to break ties). Empty when no prefix matches.
    Both are empty when no last name could be parsed.
    """
    first, last = _ev_name_parts(_ev_clean_name(display_name))
    if not last:
        return [], []
    same_last = [
        c for c in contacts if (c.familyName or "").strip().lower() == last.lower()
    ]
    matches = [
        c
        for c in same_last
        if n > 0 and (c.firstName or "")[:n].lower() == first[:n].lower()
    ]
    # If multiple candidates survive, retry with n+1 and n+2 to break ties
    for stricter_n in range(n + 1, n + 3):
        if len(matches) <= 1:
            break
        narrowed = [
            c
            for c in same_last
            if (c.firstName or "")[:stricter_n].lower() == first[:stricter_n].lower()
        ]
        if narrowed:
            matches = narrowed
    return matches, same_last


def _ev_suggest_matches(
    candidates: list[ContactDetails],
    unconnected_users: list[User],
    n: int = EASYVEREIN_MATCH_FIRST_NAME_CHARS,
) -> dict[str, list[dict]]:
    """Suggest EV-contact matches for pybarsys users without an EasyVerein link.

    Returns {"user", "contact", "checked"} dicts as user->contact match suggestions split into two buckets:
      - "high": a unique full match (family name + first-name prefix) - pre-checked.
      - "low": ambiguous full matches, or (when there is no full match) every contact
        sharing the family name - offered unchecked as weak hints.
    """
    high_confidence_suggestions: list[dict] = []
    low_confidence_suggestions: list[dict] = []
    for user in unconnected_users:
        full_matches, same_family_name_matches = _ev_match_contacts(
            candidates, user.display_name, n
        )
        if full_matches:
            is_unique_match = len(full_matches) == 1
            for contact in full_matches:
                target = (
                    high_confidence_suggestions
                    if is_unique_match
                    else low_confidence_suggestions
                )
                target.append(
                    {"user": user, "contact": contact, "checked": is_unique_match}
                )
        else:
            # No first-name match - offer every contact sharing the family name as a weak hint
            for contact in same_family_name_matches:
                low_confidence_suggestions.append(
                    {"user": user, "contact": contact, "checked": False}
                )
    return {"high": high_confidence_suggestions, "low": low_confidence_suggestions}


def _ev_rank_contacts_for_name(
    contacts: list[ContactDetails],
    display_name: str,
    n: int = EASYVEREIN_MATCH_FIRST_NAME_CHARS,
) -> list[dict]:
    """Rank EV contacts for a single entered name, in three tiers.

    Returns a list of {"contact", "url", "is_match"} dicts, ordered: strong matches
    (family name + first-name prefix, is_match=True) first, then contacts sharing only
    the family name, then everything else. Each tier is sorted by name.
    """
    full_matches, same_family_name_matches = _ev_match_contacts(
        contacts, display_name, n
    )
    full_match_ids = {c.id for c in full_matches}
    same_family_name_ids = {c.id for c in same_family_name_matches}

    def sort_key(c):
        return ((c.familyName or "").lower(), (c.firstName or "").lower())

    def row(c):
        return {
            "contact": c,
            "url": _ev_contact_url(c.id),
            "is_match": c.id in full_match_ids,
        }

    tier_full_match = sorted(
        [c for c in contacts if c.id in full_match_ids], key=sort_key
    )
    tier_same_family = sorted(
        [
            c
            for c in contacts
            if c.id in same_family_name_ids and c.id not in full_match_ids
        ],
        key=sort_key,
    )
    # Excludes the full same-family-name set, which already covers the full matches
    # (every full match shares the family name, so it is in same_family_name_ids too).
    tier_others = sorted(
        [c for c in contacts if c.id not in same_family_name_ids], key=sort_key
    )
    return [row(c) for c in tier_full_match + tier_same_family + tier_others]


class SiteSettingsView(UserIsAdminMixin, View):
    template_name = "barsys/admin/site_settings.html"

    def _render(
        self, request: HttpRequest, form: SiteSettingsForm, extra_context: dict = None
    ) -> HttpResponse:
        context = {
            "form": form,
            "pybarsys_preferences": PybarsysPreferences,
        }
        if extra_context:
            context.update(extra_context)
        return render(request, self.template_name, context)

    def get(self, request: HttpRequest) -> HttpResponse:
        return self._render(request, SiteSettingsForm(instance=SiteSettings.get()))

    def post(self, request: HttpRequest) -> HttpResponse:
        action = request.POST.get("action")

        if action == "fetch_bank_accounts":
            form = SiteSettingsForm(instance=SiteSettings.get())
            try:
                accounts = _ev_fetch_bank_accounts()
                return self._render(request, form, {"bank_accounts": accounts})
            except Exception as e:
                messages.error(
                    request,
                    "Error fetching bank accounts from EasyVerein: {}".format(e),
                )
            return self._render(request, form)

        form = SiteSettingsForm(request.POST, instance=SiteSettings.get())
        if form.is_valid():
            form.save()
            messages.success(request, "Settings saved.")
        return self._render(request, form)


def _get_ev_api() -> EasyvereinAPI:
    """Return an EasyvereinAPI instance using the token stored in SiteSettings."""

    def _on_token_refresh(new_token) -> None:
        settings = SiteSettings.get()
        settings.easyverein_api_token = new_token.Bearer
        settings.save()

    site_settings = SiteSettings.get()
    return EasyvereinAPI(
        api_key=site_settings.easyverein_api_token,
        auto_retry=True,
        auto_refresh_token=True,
        token_refresh_callback=_on_token_refresh,
    )


def _ev_fetch_bank_accounts() -> list[dict]:
    """Fetch EasyVerein bank accounts (the resource selectionAcc references).

    The python-easyverein library does not wrap the /bank-account endpoint, so we
    fetch it via the raw client. Returns a list of {"id", "name"} dicts.
    """
    ev = _get_ev_api()
    url = ev.invoice.c.get_url("/bank-account", {"limit": 100})
    response = ev.invoice.c.fetch_paginated(url, 100)
    return [{"id": acc.get("id"), "name": acc.get("name")} for acc in response.result]


class EasyVereinSyncUsersView(UserIsAdminMixin, TemplateView):
    template_name = "barsys/admin/easyverein_sync_users.html"

    def post(self, request, *args, **kwargs) -> HttpResponse:
        context = self.get_context_data(**kwargs)
        action = request.POST.get("action")
        if action == "pull":
            try:
                context["contact_details"] = self._fetch_contact_details()
            except Exception as e:
                messages.error(
                    request,
                    "Error fetching contact details from EasyVerein: {}".format(e),
                )
        elif action == "save_matches":
            saved = []
            parsed = []
            for entry in request.POST.getlist("confirm_match"):
                try:
                    user_pk, contact_id, contact_name = entry.split("|", 2)
                    contact_url = _ev_contact_url(contact_id)
                    parsed.append(
                        (User.objects.get(pk=int(user_pk)), contact_url, contact_name)
                    )
                except Exception as e:
                    messages.error(request, "Could not parse match entry: {}".format(e))
            seen_pks: set = set()
            seen_urls: set = set()
            duplicate_pks = {
                user.pk
                for user, _, _ in parsed
                if user.pk in seen_pks or seen_pks.add(user.pk)
            }
            duplicate_urls = {
                url for _, url, _ in parsed if url in seen_urls or seen_urls.add(url)
            }
            skipped: list[str] = [
                "{} -> {}".format(contact_name, user.display_name)
                for user, url, contact_name in parsed
                if user.pk in duplicate_pks or url in duplicate_urls
            ]
            if skipped:
                messages.error(
                    request,
                    "Not saved due to duplicates: {}".format(", ".join(skipped)),
                )
            for user, contact_url, contact_name in [
                t
                for t in parsed
                if t[0].pk not in duplicate_pks and t[1] not in duplicate_urls
            ]:
                try:
                    user.easyverein_contact_details_url = contact_url
                    user.save()
                    saved.append(
                        {"user_name": user.display_name, "contact_name": contact_name}
                    )
                except Exception as e:
                    messages.error(
                        request,
                        "Could not save match for {}: {}".format(user.display_name, e),
                    )
            context["saved_matches"] = saved
            if saved:
                messages.success(request, "Saved {} match(es).".format(len(saved)))
        elif action == "match":
            try:
                all_contacts = self._fetch_contact_details()
                if request.POST.get("match_scope") == "selected_only":
                    selected = set(request.POST.getlist("selected_contacts"))
                    candidates = [c for c in all_contacts if str(c.id) in selected]
                else:
                    candidates = all_contacts
                assigned_urls = set(
                    User.objects.attached_to_easyverein().values_list(
                        "easyverein_contact_details_url", flat=True
                    )
                )
                candidates = [
                    c for c in candidates if _ev_contact_url(c.id) not in assigned_urls
                ]
                context["candidates"] = candidates
                unconnected_users = list(
                    User.objects.active()
                    .buyers()
                    .pay_themselves()
                    .not_attached_to_easyverein()
                )
                context["unconnected_users"] = unconnected_users
                suggestions = _ev_suggest_matches(candidates, unconnected_users)
                context["high_confidence_suggestions"] = suggestions["high"]
                context["low_confidence_suggestions"] = suggestions["low"]
                context["high_confidence_user_pks"] = {
                    s["user"].pk for s in suggestions["high"]
                }
                context["high_confidence_contact_ids"] = {
                    s["contact"].id for s in suggestions["high"]
                }
            except Exception as e:
                messages.error(
                    request,
                    "Error fetching contact details from EasyVerein: {}".format(e),
                )
        return self.render_to_response(context)

    def _fetch_contact_details(self) -> list[ContactDetails]:
        """Return non-deleted, non-company EasyVerein contact-details as model objects.

        Company contacts are skipped: they carry only a companyName (no first/family
        name), so they can't be name-matched to Pybarsys users.
        """
        ev = _get_ev_api()
        contacts = ev.contact_details.get_all(
            search=ContactDetailsFilter(deleted=False), limit_per_page=100
        )
        return [c for c in contacts if not c.isCompany]


class EasyVereinInvoiceCreateView(UserIsAdminMixin, edit.FormView):
    template_name = "barsys/admin/easyverein_invoice_new.html"
    form_class = EasyVereinInvoicesCreateForm
    success_url = reverse_lazy("admin_easyverein_invoice_new")

    def get_initial(self) -> dict:
        initial = super().get_initial()
        user_pk = self.request.GET.get("user")
        if user_pk:
            initial["users"] = [user_pk]
        return initial

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)

        # Active buyers who pay themselves but have no EasyVerein link - they won't appear in the form
        not_attached = (
            User.objects.active().buyers().pay_themselves().not_attached_to_easyverein()
        )
        rows = [
            {
                "user": user,
                "account_balance": user.account_balance(),
                "num_unbilled_purchases": user.purchases().unbilled().count(),
            }
            for user in not_attached
        ]
        context["not_attached_users"] = sorted(
            rows, key=lambda row: row["account_balance"]
        )
        return context

    def form_valid(self, form: EasyVereinInvoicesCreateForm) -> HttpResponse:
        users = form.cleaned_data["users"]
        job_id = _ev_invoice_start_job(
            user_ids=list(users.values_list("pk", flat=True)),
            comment=form.cleaned_data["comment"],
        )
        return redirect("admin_easyverein_invoice_progress", job_id=job_id)


# --- EasyVerein invoice creation jobs (background-thread progress tracking) ---
# In-process registry: works because we run a single gunicorn worker. If the
# deployment ever scales to multiple workers, this must move to a shared store
# (cache/DB), since a poll could hit a worker that does not hold the job.
# TODO: also lost on restart (progress poll 404s mid-job; data itself is safe) and
# entries are never evicted (slow unbounded growth). Deferred - a cache/DB-backed
# store would fix restart-survival, multi-worker, and cleanup together.
_ev_invoice_jobs: dict[str, dict] = {}
_ev_invoice_jobs_lock = threading.Lock()


def _ev_invoice_job_snapshot(job_id: str) -> dict | None:
    """Return a shallow copy of the job state, or None if the job is unknown."""
    with _ev_invoice_jobs_lock:
        job = _ev_invoice_jobs.get(job_id)
        return dict(job) if job is not None else None


def _ev_invoice_start_job(user_ids: list[int], comment: str) -> str:
    """Register a job and start a background thread that processes it."""
    job_id = uuid.uuid4().hex
    with _ev_invoice_jobs_lock:
        _ev_invoice_jobs[job_id] = {
            "total": len(user_ids),
            "done": 0,
            "status": "running",
            "results": [],
            "status_message": "",
        }
    threading.Thread(
        target=_ev_invoice_run_job,
        args=(job_id, user_ids, comment),
        daemon=True,
    ).start()
    return job_id


def _ev_job_set_message(job_id: str, message: str) -> None:
    with _ev_invoice_jobs_lock:
        if job_id in _ev_invoice_jobs:
            _ev_invoice_jobs[job_id]["status_message"] = message


def _ev_invoice_run_job(job_id: str, user_ids: list[int], comment: str) -> None:
    """Background worker: create an EasyVerein invoice per user, updating progress.

    Runs in its own thread, so it owns (and closes) its DB connection.
    """
    try:
        users = list(User.objects.filter(pk__in=user_ids))
        results = []
        mail_conn = view_helpers.EmailConnectionWrapper(fake_sending_mails=False)
        for user in users:
            _ev_job_set_message(job_id, "Processing {}…".format(user.display_name))
            try:
                results.append(_ev_create_invoice_for_user(user, comment, mail_conn))
            except Exception as e:
                results.append(
                    {"user": user.display_name, "ok": False, "detail": str(e)}
                )
            with _ev_invoice_jobs_lock:
                _ev_invoice_jobs[job_id]["done"] += 1
                _ev_invoice_jobs[job_id]["results"] = list(results)
                _ev_invoice_jobs[job_id]["status_message"] = ""
        with _ev_invoice_jobs_lock:
            _ev_invoice_jobs[job_id]["status"] = "finished"
            _ev_invoice_jobs[job_id]["results"] = results
    except Exception as e:
        with _ev_invoice_jobs_lock:
            if job_id in _ev_invoice_jobs:
                _ev_invoice_jobs[job_id]["status"] = "error"
                _ev_invoice_jobs[job_id]["error"] = str(e)
    finally:
        connection.close()


def _ev_invoice_description(invoice: Invoice, comment: str) -> str:
    """Render the EasyVerein invoice description (HTML) listing billed purchases.

    Reuses the same purchase sub-template as the normal invoice email; the language
    follows the configured e-mail template dir. EasyVerein renders this as HTML.
    """
    return render_to_string(
        os.path.join(
            PybarsysPreferences.EMAIL.TEMPLATE_DIR, "ev_invoice_description.html.html"
        ),
        {
            "invoice": invoice,
            "own_purchases": invoice.own_purchases(),
            "other_purchases_grouped": invoice.other_purchases_grouped(),
            "comment": comment,
            "pybarsys_preferences": PybarsysPreferences,
        },
    ).strip()


def _ev_create_invoice_for_user(
    user: User, comment: str, mail_conn: view_helpers.EmailConnectionWrapper
) -> dict:
    """Create a draft EasyVerein invoice for one user and mirror it on the pybarsys side.

    EasyVerein invoice positions (signed so that positive = the user owes the bar):
      - carried account balance (-account_balance)
      - own unbilled purchases
      - unbilled purchases per dependant (one position each)
      - already-made deposits (-unbilled payments)
    The invoice sum must be positive, so a net credit becomes an "expense" (Ausgabe)
    invoice with negated lines. On the pybarsys side a single invoice captures the
    unbilled purchases/payments plus a virtual payment that zeroes the balance - its
    amount equals the (signed) EasyVerein total.

    Pybarsys is written first (quick), then the EasyVerein draft is created. If the
    EasyVerein call fails, the pybarsys invoice + virtual payment are deleted again
    (which un-bills the affected purchases/payments via SET_NULL).
    """
    result = {"user": user.display_name, "ok": False, "detail": ""}

    contact_url = user.easyverein_contact_details_url
    if not contact_url:
        result["detail"] = "no EasyVerein link"
        return result

    # --- components (read-only) ---
    balance = user.account_balance()  # B; negative = debt
    own_sum = user.purchases().unbilled().sum_cost()  # S
    deposits = user.payments().unbilled().sum_amount()  # P
    dependant_purchases = Purchase.objects.unbilled().filter(
        user__purchases_paid_by_other=user
    )
    dep_groups = []  # [(dependant, sum)]
    for dep in User.objects.filter(purchases_paid_by_other=user).order_by(
        "display_name"
    ):
        dep_sum = dependant_purchases.filter(user=dep).sum_cost()
        if dep_sum:
            dep_groups.append((dep, dep_sum))
    dep_total = sum((s for _, s in dep_groups), Decimal("0"))

    ev_total = -balance + own_sum + dep_total - deposits
    # Skip only when there is genuinely nothing to bill. A total of 0 with non-zero
    # components (e.g. a credit balance cancelling purchases) is billed on purpose:
    # the purchases/payments still need to be marked billed on the pybarsys side, and
    # EasyVerein accepts the resulting zero-total invoice (verified in practice).
    if balance == 0 and own_sum == 0 and dep_total == 0 and deposits == 0:
        result["ok"] = True
        result["detail"] = "skipped: nothing to transfer"
        return result

    # --- signed line items (positive = user owes the bar) ---
    items_signed = []  # [(description, Decimal amount)]
    if balance:
        items_signed.append(("Kontostand-Übertrag (Pybarsys)", -balance))
    if own_sum:
        items_signed.append(("Eigene Einkäufe", own_sum))
    for dep, dep_sum in dep_groups:
        items_signed.append(("Einkäufe von {}".format(dep.display_name), dep_sum))
    if deposits:
        items_signed.append(("Noch nicht abgerechnete Zahlungen (Pybarsys)", -deposits))

    # The invoice sum must be positive: bill as revenue when owed, else as
    # credit (Gutschrift) with negated lines so the total is positive.
    if ev_total > 0:
        kind, sign = "revenue", Decimal("1")
    else:
        kind, sign = "credit", Decimal("-1")

    ev = _get_ev_api()
    site_settings = SiteSettings.get()
    invoice = None
    virtual_payment = None
    ev_invoice = None
    notif_failures: list[str] = []
    notif_success: list[str] = []
    try:
        # 1) pybarsys side first (quick; no transaction held across the API call)
        invoice = Invoice.objects.create_for_user(user)
        virtual_payment = Payment.objects.create(
            user=user,
            amount=ev_total,  # signed; zeroes the account balance
            invoice=invoice,
            payment_method=Payment.PAYMENT_METHOD_OTHER,
            comment="Balance transferred to EasyVerein",
            is_virtual_payment=True,
        )
        invoice.amount_payments += ev_total
        invoice.save()

        # 2) EasyVerein draft invoice (with positions)
        inv_number = "Pybarsys Inv{} U{} {}".format(
            invoice.pk, user.pk, invoice.created_date.strftime("%Y-%m-%d")
        )
        description = _ev_invoice_description(invoice, comment)
        ev_invoice = ev.invoice.create_with_items(
            InvoiceCreate(
                isDraft=True,
                kind=kind,
                relatedAddress=contact_url,
                # No bank account on credit invoices (the bar pays the user)
                selectionAcc=(
                    site_settings.easyverein_bank_account_id
                    if kind == "revenue"
                    else None
                ),
                totalPrice=float(ev_total * sign),
                invNumber=inv_number,
                # payer quotes this as the bank-transfer reference
                refNumber=inv_number,
                description=description or None,
                paymentInformation="account",
            ),
            [
                InvoiceItemCreate(
                    title=desc,
                    description="",
                    quantity=1,
                    unitPrice=float(amount * sign),
                    totalPrice=float(amount * sign),
                )
                for desc, amount in items_signed
            ],
            # set_draft_state=True finalizes the invoice (sends it out);
            # False keeps it as a draft regardless of isDraft.
            set_draft_state=site_settings.easyverein_finalize_invoices,
        )

        # 3) link the pybarsys invoice back to the EasyVerein invoice
        invoice.comment = (
            f"Transferred to Easyverein with invoice ID {ev_invoice.id} ({inv_number})"
        )
        if comment:
            invoice.comment += " — {}".format(comment)
        invoice.save()

        # 4) notify dependants whose purchases are included
        for dependant, dep_purchases in invoice.other_purchases_grouped():
            msg = view_helpers.generate_email_purchase_notification(
                dependant, dep_purchases, invoice
            )
            if mail_conn.send_message(msg):
                notif_success.append(dependant.display_name)
            else:
                notif_failures.append(
                    "{}: {}".format(dependant.display_name, mail_conn.last_error)
                )
    except Exception as e:
        # roll back: delete EV draft (best effort) + pybarsys invoice/payment.
        # Delete the virtual payment before the invoice; deleting the invoice
        # un-bills the real purchases/payments via SET_NULL.
        if ev_invoice is not None:
            try:
                ev.invoice.delete(ev_invoice)
            except Exception:
                pass
        if virtual_payment is not None:
            virtual_payment.delete()
        if invoice is not None:
            invoice.delete()
        result["detail"] = "failed, rolled back: {}".format(e)
        return result

    result["ok"] = True
    result["detail"] = "EV invoice '{}' — {} {}".format(
        inv_number, kind, currency(ev_total * sign)
    )
    if notif_success:
        result["detail"] += " | notified dependants: {}".format(
            ", ".join(notif_success)
        )
    if notif_failures:
        result["detail"] += " | dependant notification failed: {}".format(
            ", ".join(notif_failures)
        )
    return result


class EasyVereinInvoiceProgressView(UserIsAdminMixin, TemplateView):
    template_name = "barsys/admin/easyverein_invoice_progress.html"

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        context["job_id"] = kwargs["job_id"]
        context["job_missing"] = _ev_invoice_job_snapshot(kwargs["job_id"]) is None
        return context


class EasyVereinInvoiceStatusView(UserIsAdminMixin, View):
    def get(self, request: HttpRequest, job_id: str) -> JsonResponse:
        job = _ev_invoice_job_snapshot(job_id)
        if job is None:
            return JsonResponse({"status": "missing"}, status=404)
        return JsonResponse(
            {
                "status": job["status"],
                "done": job["done"],
                "total": job["total"],
                "results": job.get("results", []),
                "error": job.get("error", ""),
                "status_message": job.get("status_message", ""),
            }
        )


# EasyVerein END


@api_view(["GET", "POST"])
def main_purchase_api(request):
    if request.method == "GET":
        purchases = Purchase.objects.all()[
            : PybarsysPreferences.Misc.NUM_MAIN_LAST_PURCHASES
        ]
        serializer = PurchaseSerializer(purchases, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    elif request.method == "POST":
        form = SingleUserSinglePurchaseForm()
        form.data = request.data.copy()
        form.is_bound = True
        if form.is_valid():
            if not form.is_free_item_purchase:
                result = purchase_no_free_item(form)
            else:
                result = purchase_free_item(form)

            serializer = PurchaseSerializer(result["purchase"])
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def main_user_api(request):
    if request.method == "GET":
        users = User.objects.buyers().active()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)


@api_view(["GET"])
def main_product_api(request):
    if request.method == "GET":
        products = Product.objects.all()
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)
