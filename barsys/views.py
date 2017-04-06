from django.shortcuts import render
from django.shortcuts import get_list_or_404, get_object_or_404, redirect
from .models import Product, Category, User, Purchase
from .forms import SingleUserSinglePurchaseForm
from .view_helpers import get_renderable_stats_elements
from constance import config
from itertools import groupby
from collections import OrderedDict


def user_purchase(request, user_id):
    user = get_object_or_404(User.objects.filter_buyers(), pk=user_id)
    categories = get_list_or_404(Category)

    if request.method == "POST":
        form = SingleUserSinglePurchaseForm(request.POST)

        if form.is_valid():
            user = User.objects.get(pk=form.cleaned_data["user_id"])
            product = Product.objects.get(pk=form.cleaned_data["product_id"])

            purchase = Purchase(user=user, product_name=product.name, product_amount=product.amount,
                                product_category=product.category.name, product_price=product.price,
                                quantity=form.cleaned_data["quantity"])
            purchase.save()
            return redirect(user_list)
        else:
            context = {"error_messages": ["Invalid form data"]}
    else:
        context = {}

    form = SingleUserSinglePurchaseForm()

    context["user"] = user
    context["categories"] = categories
    context["form"] = form

    return render(request, "barsys/user_purchase.html", context)


def user_list(request):
    all_users_ungrouped = User.objects.filter_buyers().order_by("display_name")

    # Group by first letter of name
    all_users = OrderedDict()
    for k, g in groupby(all_users_ungrouped, key=lambda u: u.display_name[0]):
        if k in all_users:
            all_users[k] += g
        else:
            all_users[k] = list(g)

    favorite_users = User.objects.filter_favorites()

    last_purchases = Purchase.objects.order_by("-created_date")[:config.NUM_MAIN_LAST_PURCHASES]

    sidebar_stats_elements = get_renderable_stats_elements()

    context = {"favorites": favorite_users,
               "all_users": all_users,
               "last_purchases": last_purchases,
               "sidebar_stats_elements": sidebar_stats_elements, }
    return render(request, 'barsys/user_list.html', context)


def user_history(request, user_id):
    user = get_object_or_404(User.objects.filter_buyers(), pk=user_id)

    # Sum not yet billed product purchases grouped by product_category
    categories = Purchase.objects.purchases_by_category_and_product(user__pk=user_id, invoice=None)

    last_purchases = Purchase.objects.filter(user__pk=user.pk).order_by("-created_date")[
                     :config.NUM_USER_PURCHASE_HISTORY]

    context = {"user": user,
               "categories": categories,
               "last_purchases": last_purchases}
    return render(request, "barsys/user_history.html", context)
