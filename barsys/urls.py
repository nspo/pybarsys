from django.conf.urls import url

from . import views, filters

urlpatterns = [
    # main page for purchasing products (main_*)
    url(r'^$', views.main_user_list, name="root"),
    url(r'^user/list/$', views.main_user_list, name="main_user_list"),
    url(r'^user/(?P<user_id>[0-9]+)/purchase/$', views.main_user_purchase, name='main_user_purchase'),
    url(r'^user/(?P<user_id>[0-9]+)/history/$', views.main_user_history, name='main_user_history'),

    # user area (user_*)
    url(r'^userarea/$', views.user_home, name='user_home'),

    # Purchase
    url(r'^userarea/purchase/$', views.PurchaseListView.as_view(), name="user_purchase_list"),
    url(r'^userarea/purchase/new/$', views.PurchaseCreateView.as_view(), name='user_purchase_new'),
    url(r'^userarea/purchase/(?P<pk>[0-9]+)/detail/$', views.PurchaseDetailView.as_view(), name='user_purchase_detail'),
    url(r'^userarea/purchase/(?P<pk>[0-9]+)/update/$', views.PurchaseUpdateView.as_view(), name='user_purchase_update'),
    url(r'^userarea/purchase/(?P<pk>[0-9]+)/delete/$', views.PurchaseDeleteView.as_view(), name='user_purchase_delete'),

    # User
    url(r'^userarea/user/$', views.UserListView.as_view(), name='user_user_list'),
    url(r'^userarea/user/new/$', views.UserCreateView.as_view(), name='user_user_new'),
    url(r'^userarea/user/(?P<pk>[0-9]+)/detail/$', views.UserDetailView.as_view(), name='user_user_detail'),
    url(r'^userarea/user/(?P<pk>[0-9]+)/update/$', views.UserUpdateView.as_view(), name='user_user_update'),
    url(r'^userarea/user/(?P<pk>[0-9]+)/delete/$', views.UserDeleteView.as_view(), name='user_user_delete'),

    # Category
    url(r'^userarea/category/$', views.CategoryListView.as_view(), name='user_category_list'),
    url(r'^userarea/category/new/$', views.CategoryCreateView.as_view(), name='user_category_new'),
    url(r'^userarea/category/(?P<pk>[0-9]+)/detail/$', views.CategoryDetailView.as_view(), name='user_category_detail'),
    url(r'^userarea/category/(?P<pk>[0-9]+)/update/$', views.CategoryUpdateView.as_view(), name='user_category_update'),
    url(r'^userarea/category/(?P<pk>[0-9]+)/delete/$', views.CategoryDeleteView.as_view(), name='user_category_delete'),

    # Product
    url(r'^userarea/product/$', views.ProductListView.as_view(), name='user_product_list'),
    url(r'^userarea/product/new/$', views.ProductCreateView.as_view(), name='user_product_new'),
    url(r'^userarea/product/(?P<pk>[0-9]+)/detail/$', views.ProductDetailView.as_view(), name='user_product_detail'),
    url(r'^userarea/product/(?P<pk>[0-9]+)/update/$', views.ProductUpdateView.as_view(), name='user_product_update'),
    url(r'^userarea/product/(?P<pk>[0-9]+)/delete/$', views.ProductDeleteView.as_view(), name='user_product_delete'),

    # Payment
    url(r'^userarea/payment/$', views.PaymentListView.as_view(), name='user_payment_list'),
    url(r'^userarea/payment/export/$', views.PaymentExportView.as_view(), name='user_payment_export'),
    url(r'^userarea/payment/new/$', views.PaymentCreateView.as_view(), name='user_payment_new'),
    url(r'^userarea/payment/(?P<pk>[0-9]+)/detail/$', views.PaymentDetailView.as_view(), name='user_payment_detail'),
    url(r'^userarea/payment/(?P<pk>[0-9]+)/update/$', views.PaymentUpdateView.as_view(), name='user_payment_update'),
    url(r'^userarea/payment/(?P<pk>[0-9]+)/delete/$', views.PaymentDeleteView.as_view(), name='user_payment_delete'),

    # StatsDisplay
    url(r'^userarea/statsdisplay/$', views.StatsDisplayListView.as_view(), name='user_statsdisplay_list'),
    url(r'^userarea/statsdisplay/new/$', views.StatsDisplayCreateView.as_view(), name='user_statsdisplay_new'),
    url(r'^userarea/statsdisplay/(?P<pk>[0-9]+)/detail/$', views.StatsDisplayDetailView.as_view(),
        name='user_statsdisplay_detail'),
    url(r'^userarea/statsdisplay/(?P<pk>[0-9]+)/update/$', views.StatsDisplayUpdateView.as_view(),
        name='user_statsdisplay_update'),
    url(r'^userarea/statsdisplay/(?P<pk>[0-9]+)/delete/$', views.StatsDisplayDeleteView.as_view(),
        name='user_statsdisplay_delete'),

    # Statistics
    url(r'^userarea/statistics/purchase/$', views.PurchaseStatisticsView.as_view(), name='user_purchase_statistics'),
]
