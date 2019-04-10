import csv
import os.path

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core import exceptions, paginator
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.text import Truncator
from django.views.generic import edit, View
from django.views.generic.detail import DetailView
from django_filters.views import FilterView
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from barsys.serializers import PurchaseSerializer, UserSerializer, ProductSerializer
from pybarsys.settings import PybarsysPreferences
from . import filters
from . import view_helpers
from .forms import *
from .templatetags.barsys_helpers import currency
from .view_helpers import get_renderable_stats_elements, get_most_bought_product_for_user, \
    get_most_bought_product_for_users


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


class UserListView(UserIsAdminMixin, FilterView):
    filterset_class = filters.UserFilter
    template_name = 'barsys/admin/user_list.html'

    paginate_by = 10


class UserExportView(UserIsAdminMixin, FilterView):
    filterset_class = filters.UserFilter

    def render_to_response(self, context, **response_kwargs):
        # Could use timezone.now(), but that makes the string much longer
        filename = "{}-pybarsys-users-export.csv".format(datetime.datetime.now().replace(microsecond=0).isoformat())

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)

        writer = csv.writer(response)
        writer.writerow(
            ['display_name', 'email', 'pays_themselves', 'account_balance', 'unbilled_purchases', 'unbilled_payments'])

        for user in self.object_list:
            writer.writerow(
                [user.display_name, user.email, user.pays_themselves(), user.account_balance(),
                 user.purchases().unbilled().sum_cost(), user.payments().unbilled().sum_amount()])

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


class UserCreateView(UserIsAdminMixin, edit.CreateView):
    model = User
    form_class = UserCreateForm
    template_name = "barsys/admin/user_new.html"


class UserUpdateView(UserIsAdminMixin, edit.UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = "barsys/admin/user_update.html"


class CheckedDeleteView(View):
    """ Base view class for calling a check on object.cannot_be_deleted() before .delete()ing it """
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
            raise exceptions.ImproperlyConfigured("No URL to redirect to. Provide a success_url.")

    def get(self, request, pk):
        self.object = get_object_or_404(self.model, pk=pk)
        context = {"object": self.object,
                   "cannot_be_deleted": self.object.cannot_be_deleted(),
                   "cancel_url": self.cancel_url}
        return render(request, self.template_name, context)


class UserDeleteView(UserIsAdminMixin, CheckedDeleteView):
    success_url = reverse_lazy('admin_user_list')
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
        return redirect('admin_purchase_list')


class PurchaseDeleteView(UserIsAdminMixin, CheckedDeleteView):
    model = Purchase
    success_url = reverse_lazy('admin_purchase_list')


# Category


class CategoryListView(UserIsAdminMixin, FilterView):
    filterset_class = filters.CategoryFilter
    template_name = 'barsys/admin/category_list.html'

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
    success_url = reverse_lazy('admin_category_list')


# Category END
# Product BEGIN

class ProductListView(UserIsAdminMixin, FilterView):
    filterset_class = filters.ProductFilter
    template_name = 'barsys/admin/product_list.html'

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
    success_url = reverse_lazy('admin_product_list')


# Product END
# StatsDisplay BEGIN

class StatsDisplayListView(UserIsAdminMixin, FilterView):
    filterset_class = filters.StatsDisplayFilter
    template_name = 'barsys/admin/statsdisplay_list.html'

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
    success_url = reverse_lazy('admin_statsdisplay_list')


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
        filename = "{}-pybarsys-payments-export.csv".format(datetime.datetime.now().replace(microsecond=0).isoformat())

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)

        writer = csv.writer(response)
        writer.writerow(['created', 'value_date', 'email', 'display_name', 'amount', 'payment_method', 'comment'])

        for obj in self.object_list:
            writer.writerow(
                [obj.created_date, obj.value_date, obj.user.email, obj.user.display_name, obj.amount,
                 obj.get_payment_method_display(),
                 obj.comment])

        return response


class PaymentDetailView(UserIsAdminMixin, DetailView):
    model = Payment
    template_name = "barsys/admin/payment_detail.html"


class PaymentCreateView(UserIsAdminMixin, edit.CreateView):
    model = Payment
    form_class = PaymentForm
    template_name = "barsys/admin/payment_new.html"


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
        return redirect('admin_payment_list')


class PaymentDeleteView(UserIsAdminMixin, CheckedDeleteView):
    model = Payment
    success_url = reverse_lazy('admin_payment_list')


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
        view_helpers.send_invoice_mails(request, [invoice])
        return redirect("admin_invoice_list")


class PaymentReminderSendView(UserIsAdminMixin, View):
    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        view_helpers.send_reminder_mails(request, [user])
        return redirect("admin_user_detail", pk=pk)


# for debugging mail

class InvoiceMailDebugView(UserIsAdminMixin, DetailView):
    model = Invoice
    template_name = os.path.join(PybarsysPreferences.EMAIL.TEMPLATE_DIR, "normal_invoice.html.html")

    def get_context_data(self, **kwargs):
        context = super(InvoiceMailDebugView, self).get_context_data(**kwargs)

        invoice = self.object

        context["invoice"] = invoice
        context["recipient"] = invoice.recipient
        context["pybarsys_preferences"] = PybarsysPreferences
        context["own_purchases"] = invoice.own_purchases()
        context["other_purchases_grouped"] = invoice.other_purchases_grouped()
        context["last_invoices"] = invoice.recipient.invoices()[:5]
        context["payments"] = invoice.payments()

        return context


class PaymentReminderMailDebugView(UserIsAdminMixin, DetailView):
    model = User
    template_name = os.path.join(PybarsysPreferences.EMAIL.TEMPLATE_DIR, "payment_reminder.html.html")

    def get_context_data(self, **kwargs):
        context = super(PaymentReminderMailDebugView, self).get_context_data(**kwargs)

        user = self.object

        context["recipient"] = user
        context["pybarsys_preferences"] = PybarsysPreferences
        context["last_invoices"] = user.invoices()[:5]
        context["last_payments"] = user.payments()[:5]

        return context


# end debugging mail


class InvoiceCreateView(UserIsAdminMixin, edit.FormView):
    template_name = "barsys/admin/invoice_new.html"
    form_class = InvoicesCreateForm
    success_url = reverse_lazy("admin_invoice_list")

    def form_valid(self, form):
        users = form.cleaned_data["users"]
        send_invoices = form.cleaned_data["send_invoices"]
        send_dependant_notifications = form.cleaned_data["send_dependant_notifications"]
        send_payment_reminders = form.cleaned_data["send_payment_reminders"]
        autolock_accounts = form.cleaned_data["autolock_accounts"]

        skipped_users = []
        invoices = []
        users_to_remind = []
        users_autolocked = []

        for user in users:

            balance_before = user.account_balance()

            if Purchase.objects.to_pay_by(user).exists() or user.payments().unbilled().exists():
                # print("{} has {} purchases to pay for: ".format(user, purchases_to_pay.count()))
                invoice = Invoice.objects.create_for_user(user)
                invoices.append(invoice)
            else:
                # print("{} has no purchases to pay for".format(user))
                if send_payment_reminders and user.account_balance() < PybarsysPreferences.Misc.BALANCE_BELOW_TRANSFER_MONEY:
                    users_to_remind.append(user)
                skipped_users.append(user)

            # remove autolock if new balance is adequate
            if user.is_autolocked and user.account_balance() > PybarsysPreferences.Misc.BALANCE_BELOW_AUTOLOCK:
                user.is_autolocked = False
                user.save()

            if autolock_accounts:
                # autolock user if necessary
                if balance_before < PybarsysPreferences.Misc.BALANCE_BELOW_AUTOLOCK and user.account_balance() < PybarsysPreferences.Misc.BALANCE_BELOW_AUTOLOCK:
                    # user has surpassed autolock threshold twice
                    user.is_autolocked = True
                    user.save()
                    users_autolocked.append(user)

        if len(invoices) > 0:
            created_str = "Created {} invoice(s) for the following user(s): {}. ".format(len(invoices), ", ".join(
                ["{} ({})".format(i.recipient.display_name, currency(i.amount_purchases - i.amount_payments)) for i in
                 invoices]))
        else:
            created_str = "No invoices were created. "
        messages.info(self.request, created_str)

        if len(skipped_users) > 0:
            # skipped_str = "Skipped {} user(s): {}".format(len(skipped_users), ' ,'.join([u.__str__() for u in skipped_users]))
            skipped_str = "Skipped {} user(s) because they did not need new invoices.".format(len(skipped_users))
            messages.info(self.request, skipped_str)

        if len(users_autolocked) > 0:
            autolocked_str = "The following users were autolocked: {}".format(
                ', '.join([u.__str__() for u in users_autolocked])
            )
            messages.warning(self.request, autolocked_str)

        # Send invoice mails if wanted
        if send_invoices and len(invoices) > 0:
            view_helpers.send_invoice_mails(self.request, invoices,
                                            send_dependant_notifications=send_dependant_notifications)
        else:
            messages.info(self.request, "No invoice mails were sent.")

        # Send payment reminder mails
        if len(users_to_remind) > 0:
            view_helpers.send_reminder_mails(self.request, users_to_remind)

        return super(InvoiceCreateView, self).form_valid(form)


class InvoiceDeleteView(UserIsAdminMixin, CheckedDeleteView):
    model = Invoice
    success_url = reverse_lazy('admin_invoice_list')


# Invoice END
# Statistics BEGIN


class PurchaseStatisticsByCategoryView(UserIsAdminMixin, FilterView):
    filterset_class = filters.PurchaseFilter
    template_name = "barsys/admin/purchase_statistics.html"
    paginate_by = 10

    metrics = {
        "num_purchases": models.Count("id"),
        "average_cost": models.Avg(F("quantity") * F("product_price"),
                                   output_field=DecimalField(decimal_places=2)),
        "average_quantity": models.Avg(F("quantity"),
                                       output_field=DecimalField(decimal_places=2)),
        "total_quantity": models.Sum(F("quantity")),
        "total_sales": models.Sum(F("quantity") * F("product_price"),
                                  output_field=DecimalField(decimal_places=2)),
    }

    def get_context_data(self, **kwargs):
        context = super(PurchaseStatisticsByCategoryView, self).get_context_data(**kwargs)

        context["title"] = "Purchase statistics grouped by category"
        context["grouped_by"] = ["product_category"]
        context["grouped_by_title"] = ["Category"]

        context["summary"] = list(
            context["filter"].qs
                .values("product_category")
                .annotate(**self.metrics)
                .order_by("-total_sales")
        )

        context["summary_total"] = dict(
            context["filter"].qs.aggregate(**self.metrics)
        )

        return context

    def get_filterset_kwargs(self, filterset_class):
        kwargs = super(PurchaseStatisticsByCategoryView, self).get_filterset_kwargs(filterset_class)
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
        context = super(PurchaseStatisticsByProductView, self).get_context_data(**kwargs)

        context["title"] = "Purchase statistics grouped by product"
        context["grouped_by"] = ["product_name", "product_amount"]
        context["grouped_by_title"] = ["Product", "Amount"]

        context["summary"] = list(
            context["filter"].qs
                .values("product_name", "product_amount")
                .annotate(**PurchaseStatisticsByCategoryView.metrics)
                .order_by("-total_sales")
        )

        context["summary_total"] = dict(
            context["filter"].qs.aggregate(**PurchaseStatisticsByCategoryView.metrics)
        )

        return context

    def get_filterset_kwargs(self, filterset_class):
        kwargs = super(PurchaseStatisticsByProductView, self).get_filterset_kwargs(filterset_class)
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
            context["filter"].qs
                .values("user", "user__display_name")
                .annotate(**PurchaseStatisticsByCategoryView.metrics)
                .order_by("-total_sales")
        )

        context["summary_total"] = dict(
            context["filter"].qs.aggregate(**PurchaseStatisticsByCategoryView.metrics)
        )

        return context

    def get_filterset_kwargs(self, filterset_class):
        kwargs = super(PurchaseStatisticsByUserView, self).get_filterset_kwargs(filterset_class)
        if kwargs["data"] is None:
            kwargs["data"] = {"is_free_item_purchase": False}
        elif "is_free_item_purchase" not in kwargs["data"]:
            kwargs["data"] = kwargs["data"].copy()
            kwargs["data"]["is_free_item_purchase"] = False

        return kwargs


class UserStatisticsByAccountBalance(FilterView):
    filterset_class = filters.UserFilter
    template_name = "barsys/admin/user_account_balance_statistics.html"
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super(UserStatisticsByAccountBalance, self).get_context_data(**kwargs)

        invoices = Invoice.objects.filter(recipient_id__in=context["filter"].qs)
        balances = invoices.values("recipient_id", "recipient__display_name").order_by("recipient_id").annotate(
            account_balance=models.Sum(F("amount_payments") - F("amount_purchases"))).order_by("account_balance")

        context["balances"] = balances
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
            context = {'title': self.new_title}
            pcs = ProductAutochangeSet()
        else:
            context = {'title': self.update_title}
            pcs = get_object_or_404(ProductAutochangeSet, pk=pk)

        formset = ProductAutochangeInlineFormSet(request.POST, request.FILES, instance=pcs, prefix="nested")
        form = ProductAutochangeSetForm(request.POST, request.FILES, instance=pcs, prefix="main")

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
            context = {'title': self.new_title}
            pcs = ProductAutochangeSet()
        else:
            context = {'title': self.update_title}
            pcs = get_object_or_404(ProductAutochangeSet, pk=pk)

        formset = ProductAutochangeInlineFormSet(instance=pcs, prefix="nested")
        form = ProductAutochangeSetForm(instance=pcs, prefix="main")

        context["form"] = form
        context["formset"] = formset
        return render(request, self.template_name, context)


class ProductAutochangeSetDeleteView(UserIsAdminMixin, CheckedDeleteView):
    model = ProductAutochangeSet
    success_url = reverse_lazy('admin_productautochangeset_list')


class ProductAutochangeSetExecuteView(UserIsAdminMixin, View):
    def get(self, request, pk):
        pacs = get_object_or_404(ProductAutochangeSet, pk=pk)

        pacs.execute()

        messages.info(request, "Successfully executed product autochange set: {}".format(pacs))
        return redirect("admin_productautochangeset_list")


class ProductAutochangeSetImportView(UserIsAdminMixin, View):
    def get(self, request, pk):
        pacs = get_object_or_404(ProductAutochangeSet, pk=pk)

        pacs.import_current_state()

        messages.info(request, "Successfully imported current state into {}".format(pacs))
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
    success_url = reverse_lazy('admin_freeitem_list')


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
                    messages.info(request, "Yay! You successfully purchased {}x {} for others! "
                                           "Anyone may now buy that for free until there's none left.".format(
                                            result['free_item'].leftover_quantity, product.name
                                            ))
            else:
                # free item purchase
                result = purchase_free_item(form)

            if form.cleaned_data["purchase_more_for_same_users"]:
                # notify user of successful purchase, so they are not confused b/c they
                # stay on the same page
                messages.info(request, "Purchase successful: {}".format(result['purchase']))

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
            messages.error(request, "The payer of this users' purchases is currently autolocked: {}".format(user))
            return redirect("main_user_list")

        categories = Category.objects.all()

        context = {}

        form = SingleUserSinglePurchaseForm()

        context["user"] = user
        context["categories"] = categories
        context["form"] = form
        context["free_items"] = FreeItem.objects.filter(purchasable=True, leftover_quantity__gte=1)

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

    purchase = Purchase(user=user, product_name=product.name, product_amount=product.amount,
                        product_category=product.category.name, product_price=product.price,
                        quantity=form.cleaned_data["quantity"], comment=comment)
    purchase.save()

    if form.cleaned_data["give_away_free"]:
        # create free item
        free_item = FreeItem.objects.create(giver=user, product=product,
                                            leftover_quantity=form.cleaned_data["quantity"],
                                            comment=form.cleaned_data["comment"], purchasable=True)
        return {'purchase': purchase, 'free_item': free_item}

    return {'purchase': purchase}
    

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

    purchase = Purchase(user=user, product_name=product.name, product_amount=product.amount,
                        product_category=product.category.name, product_price=Decimal(0),
                        quantity=quantity, comment=comment, is_free_item_purchase=True,
                        free_item_description=Truncator(free_item.verbose_str()).chars(120))
    purchase.save()
    return {'purchase': purchase}


class MainUserListView(View):
    def get(self, request):
        all_users_ungrouped = User.objects.active().buyers().order_by("display_name")

        # Group by first letter of name
        all_users = view_helpers.group_users(all_users_ungrouped)

        jump_to_data_lines = view_helpers.get_jump_to_data_lines(all_users)

        favorite_users = User.objects.active().buyers().favorites()

        last_purchases = Purchase.objects.order_by("-created_date")[:PybarsysPreferences.Misc.NUM_MAIN_LAST_PURCHASES]

        sidebar_stats_elements = get_renderable_stats_elements()

        context = {"favorites": favorite_users,
                   "all_users": all_users,
                   "last_purchases": last_purchases,
                   "sidebar_stats_elements": sidebar_stats_elements,
                   "jump_to_data_lines": jump_to_data_lines}
        return render(request, 'barsys/main/user_list.html', context)


class MainUserListMultiBuyView(View):
    def get(self, request):
        all_users_ungrouped = User.objects.active().buyers().order_by("display_name")

        # Group by first letter of name
        all_users = view_helpers.group_users(all_users_ungrouped)

        jump_to_data_lines = view_helpers.get_jump_to_data_lines(all_users)

        favorite_users = User.objects.active().buyers().favorites()

        last_purchases = Purchase.objects.order_by("-created_date")[:PybarsysPreferences.Misc.NUM_MAIN_LAST_PURCHASES]

        sidebar_stats_elements = get_renderable_stats_elements()

        context = {"favorites": favorite_users,
                   "all_users": all_users,
                   "last_purchases": last_purchases,
                   "sidebar_stats_elements": sidebar_stats_elements,
                   "jump_to_data_lines": jump_to_data_lines}
        return render(request, 'barsys/main/user_list_multibuy.html', context)

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
        """ Return queryset of users in user_pkey_str if all IDs are valid, or None otherwise """
        try:
            user_pks = [int(n) for n in user_pkey_str.split("/")]
        except ValueError:
            messages.error(request, "Invalid format of user IDs")
            return None

        all_users = User.objects.active().buyers().filter(pk__in=user_pks)
        if all_users.count() is not len(user_pks):
            # Not all users could be found
            messages.error(request, "Not all requested users are active buyers")
            return None

        users = all_users.filter(is_autolocked=False)
        if users.count() is not len(user_pks):
            messages.error(request, "Some users are currently autolocked: {}".format(
                ', '.join(u.__str__() for u in all_users.exclude(is_autolocked=False))
            ))
            return None

        cond_autolock2 = Q(purchases_paid_by_other=None) | Q(purchases_paid_by_other__is_autolocked=False)
        users = all_users.filter(cond_autolock2)
        if users.count() is not len(user_pks):
            messages.error(request, "The payers of some users' purchases are currently autolocked: {}".format(
                ', '.join(u.__str__() for u in all_users.exclude(cond_autolock2))
            ))
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
        context["free_items"] = FreeItem.objects.filter(purchasable=True, leftover_quantity__gte=1)
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
                    purchase = Purchase(user=user, product_name=product.name, product_amount=product.amount,
                                        product_category=product.category.name, product_price=product.price,
                                        quantity=quantity, comment=comment)
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
                    purchase = Purchase(user=user, product_name=product.name, product_amount=product.amount,
                                        product_category=product.category.name, product_price=Decimal(0),
                                        quantity=quantity_per_user, comment=comment, is_free_item_purchase=True,
                                        free_item_description=Truncator(free_item.verbose_str()).chars(120))
                    purchase.save()
            if form.cleaned_data["purchase_more_for_same_users"]:
                messages.info(request, "Successfully purchased {}x {} ({}) for the following users: {}".format(
                    purchase.quantity, purchase.product_name, currency(purchase.cost()),
                    ", ".join(u.display_name for u in users)))

                return redirect("main_user_purchase_multibuy", user_pkey_str=user_pkey_str)
            else:
                return redirect("main_user_list")
        else:
            messages.error(request, form.errors)
            return redirect("main_user_purchase_multibuy", user_pkey_str=user_pkey_str)


class MainUserHistoryView(View):
    def get(self, request, user_id):
        user = get_object_or_404(User.objects.active().buyers(), pk=user_id)

        # Sum not yet billed product purchases grouped by product_category
        categories = Purchase.objects.filter(user_id=user_id, invoice=None).stats_purchases_by_category_and_product()

        last_purchases = Purchase.objects.filter(user_id=user_id).order_by("-created_date")[
                         :PybarsysPreferences.Misc.NUM_USER_PURCHASE_HISTORY]

        if user.invoices().exists():
            last_invoice = user.invoices()[0]
        else:
            last_invoice = None

        context = {"user": user,
                   "categories": categories,
                   "last_purchases": last_purchases,
                   "last_invoice": last_invoice,
                   "pybarsys_preferences": PybarsysPreferences}
        return render(request, "barsys/main/user_history.html", context)


@api_view(['GET', 'POST'])
def main_purchase_api(request):
    if request.method == 'GET':
        purchases = Purchase.objects.all()[:PybarsysPreferences.Misc.NUM_MAIN_LAST_PURCHASES]
        serializer = PurchaseSerializer(purchases, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    elif request.method == 'POST':
        form = SingleUserSinglePurchaseForm()
        form.data = request.data.copy()
        form.is_bound = True
        if form.is_valid():
            if not form.is_free_item_purchase:
                result = purchase_no_free_item(form)
            else:
                result = purchase_free_item(form)

            serializer = PurchaseSerializer(result['purchase'])
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def main_user_api(request):
    if request.method == 'GET':
        users = User.objects.buyers().active()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)


@api_view(['GET'])
def main_product_api(request):
    if request.method == 'GET':
        products = Product.objects.all()
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)
