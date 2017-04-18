from django.conf.urls import url

from . import views

urlpatterns = [
    # main page for purchasing products (main_*)
    url(r'^$', views.MainUserListView.as_view(), name="root"),
    url(r'^user/list/$', views.MainUserListView.as_view(), name="main_user_list"),

    url(r'^multibuy/user/list/$', views.MainUserListMultiBuyView.as_view(), name="main_user_list_multibuy"),
    url(r'^multibuy/user/(?P<user_pkey_str>[0-9/]+)/purchase/$', views.MainUserPurchaseMultiBuyView.as_view(),
        name='main_user_purchase_multibuy'),

    url(r'^user/(?P<user_id>[0-9]+)/purchase/$', views.MainUserPurchaseView.as_view(), name='main_user_purchase'),
    url(r'^user/(?P<user_id>[0-9]+)/history/$', views.MainUserHistoryView.as_view(), name='main_user_history'),

    # user area (user_*)
    url(r'^admin/$', views.PurchaseListView.as_view(), name='user_home'),

    # Purchase
    url(r'^admin/purchase/list/$', views.PurchaseListView.as_view(), name="admin_purchase_list"),
    url(r'^admin/purchase/new/$', views.PurchaseCreateView.as_view(), name='admin_purchase_new'),
    url(r'^admin/purchase/(?P<pk>[0-9]+)/detail/$', views.PurchaseDetailView.as_view(), name='admin_purchase_detail'),
    url(r'^admin/purchase/(?P<pk>[0-9]+)/update/$', views.PurchaseUpdateView.as_view(), name='admin_purchase_update'),
    url(r'^admin/purchase/(?P<pk>[0-9]+)/delete/$', views.PurchaseDeleteView.as_view(), name='admin_purchase_delete'),

    # User
    url(r'^admin/user/list/$', views.UserListView.as_view(), name='admin_user_list'),
    url(r'^admin/user/export/$', views.UserExportView.as_view(), name='admin_user_export'),
    url(r'^admin/user/new/$', views.UserCreateView.as_view(), name='admin_user_new'),
    url(r'^admin/user/(?P<pk>[0-9]+)/detail/$', views.UserDetailView.as_view(), name='admin_user_detail'),
    url(r'^admin/user/(?P<pk>[0-9]+)/update/$', views.UserUpdateView.as_view(), name='admin_user_update'),
    url(r'^admin/user/(?P<pk>[0-9]+)/delete/$', views.UserDeleteView.as_view(), name='admin_user_delete'),

    # Category
    url(r'^admin/category/list/$', views.CategoryListView.as_view(), name='admin_category_list'),
    url(r'^admin/category/new/$', views.CategoryCreateView.as_view(), name='admin_category_new'),
    url(r'^admin/category/(?P<pk>[0-9]+)/detail/$', views.CategoryDetailView.as_view(), name='admin_category_detail'),
    url(r'^admin/category/(?P<pk>[0-9]+)/update/$', views.CategoryUpdateView.as_view(), name='admin_category_update'),
    url(r'^admin/category/(?P<pk>[0-9]+)/delete/$', views.CategoryDeleteView.as_view(), name='admin_category_delete'),

    # Product
    url(r'^admin/product/list/$', views.ProductListView.as_view(), name='admin_product_list'),
    url(r'^admin/product/new/$', views.ProductCreateView.as_view(), name='admin_product_new'),
    url(r'^admin/product/(?P<pk>[0-9]+)/detail/$', views.ProductDetailView.as_view(), name='admin_product_detail'),
    url(r'^admin/product/(?P<pk>[0-9]+)/update/$', views.ProductUpdateView.as_view(), name='admin_product_update'),
    url(r'^admin/product/(?P<pk>[0-9]+)/delete/$', views.ProductDeleteView.as_view(), name='admin_product_delete'),

    # Payment
    url(r'^admin/payment/list/$', views.PaymentListView.as_view(), name='admin_payment_list'),
    url(r'^admin/payment/export/$', views.PaymentExportView.as_view(), name='admin_payment_export'),
    url(r'^admin/payment/new/$', views.PaymentCreateView.as_view(), name='admin_payment_new'),
    url(r'^admin/payment/(?P<pk>[0-9]+)/detail/$', views.PaymentDetailView.as_view(), name='admin_payment_detail'),
    url(r'^admin/payment/(?P<pk>[0-9]+)/update/$', views.PaymentUpdateView.as_view(), name='admin_payment_update'),
    url(r'^admin/payment/(?P<pk>[0-9]+)/delete/$', views.PaymentDeleteView.as_view(), name='admin_payment_delete'),

    # Invoice
    url(r'^admin/invoice/list/$', views.InvoiceListView.as_view(), name='admin_invoice_list'),
    url(r'^admin/invoice/new/$', views.InvoiceCreateView.as_view(), name='admin_invoice_new'),
    url(r'^admin/invoice/(?P<pk>[0-9]+)/detail/$', views.InvoiceDetailView.as_view(), name='admin_invoice_detail'),
    url(r'^admin/invoice/(?P<pk>[0-9]+)/resend/$', views.InvoiceResendView.as_view(), name='admin_invoice_resend'),

    # Mail debug
    url(r'^admin/invoice/(?P<pk>[0-9]+)/mail/$', views.InvoiceMailDebugView.as_view(), name='admin_invoice_mail'),
    url(r'^admin/user/(?P<pk>[0-9]+)/payment_reminder$', views.PaymentReminderMailDebugView.as_view(), name='admin_user_payment_reminder'),
    # Mail debug END

    url(r'^admin/invoice/(?P<pk>[0-9]+)/delete/$', views.InvoiceDeleteView.as_view(), name='admin_invoice_delete'),

    # StatsDisplay
    url(r'^admin/statsdisplay/list/$', views.StatsDisplayListView.as_view(), name='admin_statsdisplay_list'),
    url(r'^admin/statsdisplay/new/$', views.StatsDisplayCreateView.as_view(), name='admin_statsdisplay_new'),
    url(r'^admin/statsdisplay/(?P<pk>[0-9]+)/detail/$', views.StatsDisplayDetailView.as_view(),
        name='admin_statsdisplay_detail'),
    url(r'^admin/statsdisplay/(?P<pk>[0-9]+)/update/$', views.StatsDisplayUpdateView.as_view(),
        name='admin_statsdisplay_update'),
    url(r'^admin/statsdisplay/(?P<pk>[0-9]+)/delete/$', views.StatsDisplayDeleteView.as_view(),
        name='admin_statsdisplay_delete'),

    # Statistics
    url(r'^admin/statistics/purchase/by_category/$', views.PurchaseStatisticsByCategoryView.as_view(),
        name='admin_purchase_statistics_by_category'),
    url(r'^admin/statistics/purchase/by_product/', views.PurchaseStatisticsByProductView.as_view(),
        name='admin_purchase_statistics_by_product'),

    # ProductChangeAction
    url(r'^admin/productchangeaction/list/$', views.ProductChangeActionListView.as_view(), name='admin_productchangeaction_list'),
    url(r'^admin/productchangeaction/new/$', views.ProductChangeActionCreateView.as_view(), name='admin_productchangeaction_new'),
    url(r'^admin/productchangeaction/(?P<pk>[0-9]+)/update/$', views.ProductChangeActionUpdateView.as_view(), name='admin_productchangeaction_update'),
    url(r'^admin/productchangeaction/(?P<pk>[0-9]+)/execute/$', views.ProductChangeActionExecuteView.as_view(), name='admin_productchangeaction_execute'),
    url(r'^admin/productchangeaction/(?P<pk>[0-9]+)/delete/$', views.ProductChangeActionDeleteView.as_view(), name='admin_productchangeaction_delete'),
]
