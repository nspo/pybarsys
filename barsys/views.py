from django.shortcuts import render
from django.shortcuts import get_list_or_404, get_object_or_404, redirect
from .models import Product, Category, User, Purchase
from .forms import SingleUserSinglePurchaseForm
from .view_helpers import get_renderable_stats_elements
from constance import config
from itertools import groupby
from collections import OrderedDict
from .forms import PurchaseForm

from django.views.generic import ListView, edit
from django.views.generic.detail import DetailView

from django.utils.decorators import method_decorator

from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required

from django_filters.views import FilterView


from . import filters


# user area test
@staff_member_required(login_url='user_login')
def user_home(request):
    return render(request,"barsys/userarea/home.html")





class UserListView(FilterView):
    filterset_class = filters.UserFilter
    template_name = 'barsys/userarea/user_list.html'

    paginate_by = 5


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class PurchaseListView(ListView):
    model = Purchase
    template_name = "barsys/userarea/purchase_list.html"
    paginate_by = 20


class PurchaseDetailView(DetailView):
    model = Purchase
    template_name = "barsys/userarea/purchase_detail.html"


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class PurchaseCreateView(edit.CreateView):
    model = Purchase
    form_class = PurchaseForm
    template_name = "barsys/userarea/purchase_new.html"

    def get_form(self, form_class=None):
        form = super(PurchaseCreateView, self).get_form(form_class)
        form.fields.pop('invoice')
        return form


@method_decorator(staff_member_required(login_url='user_login'), name='dispatch')
class PurchaseUpdateView(edit.UpdateView):
    model = Purchase
    form_class = PurchaseForm
    template_name = "barsys/userarea/purchase_update.html"


# user area end

def main_user_purchase(request, user_id):
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
            return redirect(main_user_list)
        else:
            context = {"error_messages": ["Invalid form data"]}
    else:
        context = {}

    form = SingleUserSinglePurchaseForm()

    context["user"] = user
    context["categories"] = categories
    context["form"] = form

    return render(request, "barsys/main/user_purchase.html", context)


def main_user_list(request):
    all_users_ungrouped = User.objects.filter_buyers().order_by("display_name")

    # Group by first letter of name
    all_users = OrderedDict()
    for k, g in groupby(all_users_ungrouped, key=lambda u: u.display_name[0].upper()):
        if k in all_users:
            all_users[k] += g
        else:
            all_users[k] = list(g)

    letter_groups_by_line = []
    # create letter_groups for jumping to existing users in view
    letter_group = OrderedDict()
    letter_group["A - C"] =  ['A', 'B', 'C']
    letter_group["D - F"] =['D', 'E', 'F']
    letter_group["G - I"] = ['G', 'H', 'I']
    letter_groups_by_line.append(letter_group)

    letter_group = OrderedDict()
    letter_group["J - L"] = ['J', 'K', 'L']
    letter_group["M - O"] = ['M', 'N', 'O']
    letter_groups_by_line.append(letter_group)

    letter_group = OrderedDict()
    letter_group["P - S"] = ['P', 'Q', 'R', 'S']
    letter_group["T - V"] =['T', 'U', 'V']
    letter_group["W - Z"] = ['W', 'X', 'Y', 'Z']
    letter_groups_by_line.append(letter_group)

    # Where the button for this group should jump to
    jump_to_data_lines = []

    for line in letter_groups_by_line:
        this_line = []
        for index_group, (title, letters) in enumerate(line.items()):
            for index_letter, letter in enumerate(letters):
                if letter in all_users:
                    # print("{} in {}, so choosing {}".format(letter, group, letter))
                    this_line.append((title, letter))
                    break
                elif index_letter + 1 == len(letters):
                    # print("{} not in {}, so choosing {}".format(letter, group, group[0]))
                    this_line.append((title, letters[0]))
                    break
        jump_to_data_lines.append(this_line)

    favorite_users = User.objects.filter_favorites()

    last_purchases = Purchase.objects.order_by("-created_date")[:config.NUM_MAIN_LAST_PURCHASES]

    sidebar_stats_elements = get_renderable_stats_elements()

    context = {"favorites": favorite_users,
               "all_users": all_users,
               "last_purchases": last_purchases,
               "sidebar_stats_elements": sidebar_stats_elements,
               "jump_to_data_lines": jump_to_data_lines,
               "other_auto_jump_goal": True }
    return render(request, 'barsys/main/user_list.html', context)


def main_user_history(request, user_id):
    user = get_object_or_404(User.objects.filter_buyers(), pk=user_id)

    # Sum not yet billed product purchases grouped by product_category
    categories = Purchase.objects.purchases_by_category_and_product(user__pk=user_id, invoice=None)

    last_purchases = Purchase.objects.filter(user__pk=user.pk).order_by("-created_date")[
                     :config.NUM_USER_PURCHASE_HISTORY]

    context = {"user": user,
               "categories": categories,
               "last_purchases": last_purchases}
    return render(request, "barsys/main/user_history.html", context)
