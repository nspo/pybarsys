from django.shortcuts import render
from django.http import Http404
from django.shortcuts import get_list_or_404, get_object_or_404, redirect
from .models import Product, Category, User, Purchase, StatsDisplay
from .forms import SingleUserSinglePurchaseForm
import datetime
from django.utils import timezone
from django.db import models
from collections import defaultdict


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
    all_users = User.objects.filter_buyers()
    favorite_users = User.objects.filter_favorites()

    try:
        last_purchases = Purchase.objects.order_by("-created_date")[:5]
    except Purchase.DoesNotExist:
        return Http404("Could not request last purchases")

    sidebar_stats_elements = get_renderable_stats_elements()

    context = {"favorites": favorite_users, "all_users": all_users, "last_purchases": last_purchases,
               "sidebar_stats_elements": sidebar_stats_elements}
    return render(request, 'barsys/user_list.html', context)


def user_history(request, user_id):
    user = get_object_or_404(User.objects.filter_buyers(), pk=user_id)

    # Sum not yet billed product purchases grouped by product_category
    categories = Purchase.objects.purchases_by_category_and_product(user__pk=user_id, invoice=None)

    last_purchases = Purchase.objects.filter(user__pk=user.pk).order_by("-created_date")[:10]

    context = dict()
    context["user"] = user
    context["categories"] = categories
    context["last_purchases"] = last_purchases
    return render(request, "barsys/user_history.html", context)


# Helpers

def get_renderable_stats_elements():
    """Create a list of dicts for all StatsDisplays that can be rendered by view more easily"""
    stats_elements = []

    all_displays = StatsDisplay.objects.order_by("-show_by_default")
    for index, stat in enumerate(all_displays):
        stats_element = dict()
        stats_element["stats_id"] = "stats_{}".format(stat.pk)
        stats_element["show_by_default"] = stat.show_by_default
        stats_element["title"] = stat.title

        # construct query filters step by step
        filters = dict()
        if stat.filter_category:
            filters["product_category"] = stat.filter_category.name
        if stat.filter_product:
            filters["product_name"] = stat.filter_product.name

        # filter by timedelta
        filters["created_date__gte"] = timezone.now() - stat.time_period

        stats_element["rows"] = []
        if stat.sort_by_and_show == StatsDisplay.SORT_BY_NUM_PURCHASES:
            top_five = Purchase.objects.purchases_by_user(**filters)[:5]
            for user, total_quantity in top_five:
                stats_element["rows"].append({"left": "{}x".format(total_quantity),
                                              "right": "{} {}".format(stat.row_string, user.display_name)})
        else:
            top_five = Purchase.objects.cost_by_user(**filters)[:5]
            for u_index, (user, total_cost) in enumerate(top_five):
                stats_element["rows"].append({"left": "{}.".format(u_index + 1),
                                              "right": "{} {}".format(stat.row_string, user.display_name)})

        if index + 1 < len(all_displays):
            # toggle next one on
            stats_element["toggle_other_on"] = "stats_{}".format(all_displays[index + 1].pk)
        else:
            # toggle first one on
            stats_element["toggle_other_on"] = "stats_{}".format(all_displays[0].pk)
        # if there is only one display, it's toggled off and on again with one click

        stats_elements.append(stats_element)

    return stats_elements
