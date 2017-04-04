from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^product/(?P<product_id>[0-9]+)/$', views.product_detail, name="product_detail"),
    url(r'^product/list/$', views.product_list, name="product_list"),
    url(r'^product/(?P<product_id>[0-9]+)/purchase/$', views.product_purchase, name='product_purchase'),
    url(r'^category/list/$', views.category_list, name="category_list"),

    url(r'^user/list/$', views.user_list, name="user_list"),
    url(r'^user/(?P<user_id>[0-9]+)/purchase/$', views.user_purchase, name='user_purchase'),
]
