from django.shortcuts import render
from django.shortcuts import get_list_or_404, get_object_or_404
from django.http import Http404
from django.http import HttpResponse
from .models import Product, Category, User

def index(request):
    return render(request, 'barsys/base.html', {})

def user_purchase(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    categories = get_list_or_404(Category)
    context = {"user" : user, "categories" : categories}
    return render(request, "barsys/user_purchase.html", context)

def user_list(request):
    users = get_list_or_404(User)
    context = {"users" : users}
    return render(request, 'barsys/user_list.html', context)

def product_detail(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        raise Http404("Product does not exist")

    return HttpResponse("{} costs {} Euro".format(product.name, product.price))

def product_purchase(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    try:
        selected_quantity = request.POST['quantity']
    except (KeyError):
        # Redisplay the question voting form.
        return render(request, 'barsys/purchase_product.html', {
            'product': product,
            'error_message': "You didn't select a quantity.",
        })
    else:
        return render(request, 'barsys/purchase_product.html', {
            'product': product,
            'error_message': "You bought a quantity of {}".format(selected_quantity),
        })

def product_list(request):
    products = Product.objects.order_by("name")
    context = {"products" : products, }
    return render(request, "barsys/product_list.html", context)

def category_list(request):
    toplevel_categories = get_list_or_404(Category, parent=None)
    context = {"toplevel_categories" : toplevel_categories}
    return render(request, "barsys/category_list.html", context)
# Create your views here.
