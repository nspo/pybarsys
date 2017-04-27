import csv

from constance import config
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core import exceptions, paginator
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.text import Truncator
from django.views.generic import edit, View
from django.views.generic.detail import DetailView
from django_filters.views import FilterView

from . import filters
from . import view_helpers
from .forms import *
from .view_helpers import get_renderable_stats_elements


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class UserListView(FilterView):
    filterset_class = filters.UserFilter
    template_name = 'barsys/admin/user_list.html'

    paginate_by = 10


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class UserExportView(FilterView):
    filterset_class = filters.UserFilter

    def render_to_response(self, context, **response_kwargs):
        # Could use timezone.now(), but that makes the string much longer
        filename = "{}-pybarsys-users-export.csv".format(datetime.datetime.now().replace(microsecond=0).isoformat())

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)

        writer = csv.writer(response)
        writer.writerow(['display_name', 'email', 'pays_themselves', 'account_balance', 'unbilled_purchases'])

        for obj in self.object_list:
            writer.writerow(
                [obj.display_name, obj.email, obj.pays_themselves(), obj.account_balance(),
                 obj.purchases().unbilled().sum_cost()])

        return response


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class UserDetailView(DetailView):
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


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class UserCreateView(edit.CreateView):
    model = User
    form_class = UserCreateForm
    template_name = "barsys/admin/user_new.html"


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class UserUpdateView(edit.UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = "barsys/admin/user_update.html"


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
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


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class UserDeleteView(CheckedDeleteView):
    success_url = reverse_lazy('admin_user_list')
    model = User


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class PurchaseListView(FilterView):
    filterset_class = filters.PurchaseFilter
    template_name = "barsys/admin/purchase_list.html"
    paginate_by = 10


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class PurchaseDetailView(DetailView):
    model = Purchase
    template_name = "barsys/admin/purchase_detail.html"


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class PurchaseCreateView(edit.CreateView):
    model = Purchase
    form_class = PurchaseForm
    template_name = "barsys/admin/purchase_new.html"


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class PurchaseUpdateView(edit.UpdateView):
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


class PurchaseDeleteView(CheckedDeleteView):
    model = Purchase
    success_url = reverse_lazy('admin_purchase_list')


# Category


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class CategoryListView(FilterView):
    filterset_class = filters.CategoryFilter
    template_name = 'barsys/admin/category_list.html'

    paginate_by = 10


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class CategoryDetailView(DetailView):
    model = Category
    template_name = "barsys/admin/category_detail.html"


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class CategoryCreateView(edit.CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "barsys/admin/category_new.html"


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class CategoryUpdateView(edit.UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "barsys/admin/category_update.html"


class CategoryDeleteView(CheckedDeleteView):
    model = Category
    success_url = reverse_lazy('admin_category_list')


# Category END
# Product BEGIN
@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class ProductListView(FilterView):
    filterset_class = filters.ProductFilter
    template_name = 'barsys/admin/product_list.html'

    paginate_by = 10


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class ProductDetailView(DetailView):
    model = Product
    template_name = "barsys/admin/product_detail.html"


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class ProductCreateView(edit.CreateView):
    model = Product
    form_class = ProductForm
    template_name = "barsys/admin/product_new.html"


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class ProductUpdateView(edit.UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "barsys/admin/product_update.html"


class ProductDeleteView(CheckedDeleteView):
    model = Product
    success_url = reverse_lazy('admin_product_list')


# Product END
# StatsDisplay BEGIN
@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class StatsDisplayListView(FilterView):
    filterset_class = filters.StatsDisplayFilter
    template_name = 'barsys/admin/statsdisplay_list.html'

    paginate_by = 10


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class StatsDisplayDetailView(DetailView):
    model = StatsDisplay
    template_name = "barsys/admin/statsdisplay_detail.html"


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class StatsDisplayCreateView(edit.CreateView):
    model = StatsDisplay
    form_class = StatsDisplayForm
    template_name = "barsys/admin/statsdisplay_new.html"


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class StatsDisplayUpdateView(edit.UpdateView):
    model = StatsDisplay
    form_class = StatsDisplayForm
    template_name = "barsys/admin/statsdisplay_update.html"


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class StatsDisplayDeleteView(CheckedDeleteView):
    model = StatsDisplay
    success_url = reverse_lazy('admin_statsdisplay_list')


# StatsDisplay END
# Payment BEGIN
@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class PaymentListView(FilterView):
    filterset_class = filters.PaymentFilter
    template_name = "barsys/admin/payment_list.html"
    paginate_by = 10


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class PaymentExportView(FilterView):
    filterset_class = filters.PaymentFilter

    def render_to_response(self, context, **response_kwargs):
        # Could use timezone.now(), but that makes the string much longer
        filename = "{}-pybarsys-payments-export.csv".format(datetime.datetime.now().replace(microsecond=0).isoformat())

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)

        writer = csv.writer(response)
        writer.writerow(['created', 'email', 'display_name', 'amount', 'payment_method', 'comment'])

        for obj in self.object_list:
            writer.writerow(
                [obj.created_date, obj.user.email, obj.user.display_name, obj.amount, obj.get_payment_method_display(),
                 obj.comment])

        return response


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class PaymentDetailView(DetailView):
    model = Payment
    template_name = "barsys/admin/payment_detail.html"


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class PaymentCreateView(edit.CreateView):
    model = Payment
    form_class = PaymentForm
    template_name = "barsys/admin/payment_new.html"


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class PaymentUpdateView(edit.UpdateView):
    model = Payment
    form_class = PaymentForm
    template_name = "barsys/admin/payment_update.html"


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class PaymentDeleteView(CheckedDeleteView):
    model = Payment
    success_url = reverse_lazy('admin_payment_list')


# PAYMENT END
# Invoice BEGIN
@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class InvoiceListView(FilterView):
    filterset_class = filters.InvoiceFilter
    template_name = "barsys/admin/invoice_list.html"
    paginate_by = 10


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class InvoiceDetailView(DetailView):
    model = Invoice
    template_name = "barsys/admin/invoice_detail.html"

    def get_context_data(self, **kwargs):
        context = super(InvoiceDetailView, self).get_context_data(**kwargs)

        context["own_purchases"] = self.object.own_purchases()
        context["other_purchases_grouped"] = self.object.other_purchases_grouped()

        return context


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class InvoiceResendView(View):
    def get(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        view_helpers.send_invoice_mails(request, [invoice])
        return redirect("admin_invoice_list")


# for debugging mail
@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class InvoiceMailDebugView(DetailView):
    model = Invoice
    template_name = "email/normal_invoice.html.html"

    def get_context_data(self, **kwargs):
        context = super(InvoiceMailDebugView, self).get_context_data(**kwargs)

        invoice = self.object

        context["invoice"] = invoice
        context["config"] = config
        context["own_purchases"] = invoice.own_purchases()
        context["other_purchases_grouped"] = invoice.other_purchases_grouped()
        context["last_invoices"] = invoice.recipient.invoices()[:5]
        context["last_payments"] = invoice.recipient.payments()[:5]

        return context


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class PaymentReminderMailDebugView(DetailView):
    model = User
    template_name = "email/payment_reminder.html.html"

    def get_context_data(self, **kwargs):
        context = super(PaymentReminderMailDebugView, self).get_context_data(**kwargs)

        user = self.object

        context["user"] = user
        context["config"] = config
        context["last_invoices"] = user.invoices()[:5]
        context["last_payments"] = user.payments()[:5]

        return context


# end debugging mail

@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class InvoiceCreateView(edit.FormView):
    template_name = "barsys/admin/invoice_new.html"
    form_class = InvoicesCreateForm
    success_url = reverse_lazy("admin_invoice_list")

    def form_valid(self, form):
        users = form.cleaned_data["users"]
        send_invoices = form.cleaned_data["send_invoices"]
        send_dependant_notifications = form.cleaned_data["send_dependant_notifications"]
        send_payment_reminders = form.cleaned_data["send_payment_reminders"]
        skipped_users = []
        invoices = []
        users_to_remind = []
        for user in users:
            purchases_to_pay = Purchase.objects.to_pay_by(user)
            if purchases_to_pay.count() > 0:
                # print("{} has {} purchases to pay for: ".format(user, purchases_to_pay.count()))
                invoice = Invoice.objects.create_for_user(user)
                invoices.append(invoice)
            else:
                # print("{} has no purchases to pay for".format(user))
                if send_payment_reminders and user.account_balance() < config.MAIL_BALANCE_SEND_MONEY:
                    users_to_remind.append(user)
                skipped_users.append(user)

        if len(invoices) > 0:
            created_str = "Created {} invoice(s) for the following user(s): {}. ".format(len(invoices), ", ".join(
                ["{} ({})".format(i.recipient.display_name, currency(i.amount)) for i in invoices]))
        else:
            created_str = "No invoices were created. "

        if len(skipped_users) > 0:
            # skipped_str = "Skipped {} user(s): {}".format(len(skipped_users), ' ,'.join([u.__str__() for u in skipped_users]))
            skipped_str = "Skipped {} user(s) because they did not need new invoices.".format(len(skipped_users))
        else:
            skipped_str = "No users were skipped because they did not need new invoices."

        messages.info(self.request, created_str + skipped_str)

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


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class InvoiceDeleteView(CheckedDeleteView):
    model = Invoice
    success_url = reverse_lazy('admin_invoice_list')


# Invoice END
# Statistics BEGIN


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class PurchaseStatisticsByCategoryView(FilterView):
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
        context["grouped_by"] = "product_category"
        context["grouped_by_title"] = "Category"

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


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class PurchaseStatisticsByProductView(FilterView):
    filterset_class = filters.PurchaseFilter
    template_name = "barsys/admin/purchase_statistics.html"
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super(PurchaseStatisticsByProductView, self).get_context_data(**kwargs)

        context["title"] = "Purchase statistics grouped by product"
        context["grouped_by"] = "product_name"
        context["grouped_by_title"] = "Product"

        context["summary"] = list(
            context["filter"].qs
                .values("product_name")
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


# Statistics END
# ProductAutochangeSet BEGIN
@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class ProductAutochangeSetListView(FilterView):
    filterset_class = filters.ProductAutochangeSetFilter
    template_name = "barsys/admin/productautochangeset_list.html"
    paginate_by = 10


class ProductAutochangeSetManageView(View):
    template_name = "barsys/admin/productautochangeset_form.html"
    new_title = "New product autochange set"
    update_title = "Update product autochange set"

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

        formset = ProductAutochangeInlineFormSet(instance=pcs, prefix="nested", )
        form = ProductAutochangeSetForm(instance=pcs, prefix="main")

        context["form"] = form
        context["formset"] = formset
        return render(request, self.template_name, context)


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class ProductAutochangeSetDeleteView(CheckedDeleteView):
    model = ProductAutochangeSet
    success_url = reverse_lazy('admin_productautochangeset_list')


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class ProductAutochangeSetExecuteView(View):
    def get(self, request, pk):
        pacs = get_object_or_404(ProductAutochangeSet, pk=pk)

        pacs.execute()

        messages.info(request, "Successfully executed product autochange set: {}".format(pacs))
        return redirect("admin_productautochangeset_list")


# ProductAutochangeSet END











# user area end



class MainUserPurchaseView(View):
    def post(self, request, user_id):
        form = SingleUserSinglePurchaseForm(request.POST)

        if form.is_valid():
            user = User.objects.get(pk=form.cleaned_data["user_id"])
            if not form.is_free_item_purchase:
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
                    messages.info(request, "Yay! You successfully purchased {}x {} for others! "
                                           "Anyone may now buy that for free until there's none left.".format(
                        free_item.leftover_quantity, product.name
                    ))

            else:
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

            return redirect("main_user_list")
        else:
            messages.error(request, form.errors)
            return redirect("main_user_purchase", user_id)

    def get(self, request, user_id):
        user = get_object_or_404(User.objects.active().buyers(), pk=user_id)
        categories = Category.objects.all()

        context = {}

        form = SingleUserSinglePurchaseForm()

        context["user"] = user
        context["categories"] = categories
        context["form"] = form
        context["free_items"] = FreeItem.objects.filter(purchasable=True, leftover_quantity__gte=1)

        return render(request, "barsys/main/user_purchase.html", context)


class MainUserListView(View):
    def get(self, request):
        all_users_ungrouped = User.objects.active().buyers().order_by("display_name")

        # Group by first letter of name
        all_users = view_helpers.group_users(all_users_ungrouped)

        jump_to_data_lines = view_helpers.get_jump_to_data_lines(all_users)

        favorite_users = User.objects.active().buyers().favorites()

        last_purchases = Purchase.objects.order_by("-created_date")[:config.NUM_MAIN_LAST_PURCHASES]

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

        last_purchases = Purchase.objects.order_by("-created_date")[:config.NUM_MAIN_LAST_PURCHASES]

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

        users = User.objects.active().buyers().filter(pk__in=user_pks)
        if users.count() is not len(user_pks):
            # Not all users could be found
            messages.error(request, "Not all requested users are active buyers")
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
            return redirect("main_user_list")
        else:
            messages.error(request, form.errors)
            return redirect("main_user_purchase_multibuy", user_pkey_str=user_pkey_str)


class MainUserHistoryView(View):
    def get(self, request, user_id):
        user = get_object_or_404(User.objects.active().buyers(), pk=user_id)

        # Sum not yet billed product purchases grouped by product_category
        categories = Purchase.objects.filter(user__pk=user_id, invoice=None).stats_purchases_by_category_and_product()

        last_purchases = Purchase.objects.filter(user__pk=user.pk).order_by("-created_date")[
                         :config.NUM_USER_PURCHASE_HISTORY]

        context = {"user": user,
                   "categories": categories,
                   "last_purchases": last_purchases,
                   "config": config}
        return render(request, "barsys/main/user_history.html", context)


# FreeItem BEGIN
@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class FreeItemListView(FilterView):
    filterset_class = filters.FreeItemFilter
    template_name = "barsys/admin/freeitem_list.html"
    paginate_by = 10


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class FreeItemCreateView(edit.CreateView):
    model = FreeItem
    form_class = FreeItemForm
    template_name = "barsys/admin/generic_form.html"

    def get_context_data(self, **kwargs):
        context = super(FreeItemCreateView, self).get_context_data(**kwargs)
        context["title"] = "New free item"
        return context


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class FreeItemUpdateView(edit.UpdateView):
    model = FreeItem
    form_class = FreeItemForm
    template_name = "barsys/admin/generic_form.html"

    def get_context_data(self, **kwargs):
        context = super(FreeItemUpdateView, self).get_context_data(**kwargs)
        context["title"] = "Update free item"
        return context


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class FreeItemDeleteView(CheckedDeleteView):
    model = FreeItem
    success_url = reverse_lazy('admin_freeitem_list')

# FreeItem END
