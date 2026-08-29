from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    path("login/", views.AMJLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),

    path("", views.dashboard, name="dashboard"),
    path("settings/shop/", views.shop_settings_view, name="shop_settings"),

    path("products/", views.product_list, name="product_list"),
    path("products/add/", views.product_add, name="product_add"),
    path("products/<int:pk>/", views.product_detail, name="product_detail"),
    path("products/<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("products/<int:pk>/delete/", views.product_delete, name="product_delete"),
    path("categories/add/", views.category_add, name="category_add"),

    path("sales/", views.sale_list, name="sale_list"),
    path("sales/add/", views.sale_add, name="sale_add"),
    path("sales/<int:pk>/edit/", views.sale_edit, name="sale_edit"),
    path("sales/<int:pk>/delete/", views.sale_delete, name="sale_delete"),
    path("sales/<int:pk>/receipt/", views.sale_receipt, name="sale_receipt"),

    path("repairs/", views.repair_list, name="repair_list"),
    path("repairs/add/", views.repair_add, name="repair_add"),
    path("repairs/<int:pk>/edit/", views.repair_edit, name="repair_edit"),
    path("repairs/<int:pk>/delete/", views.repair_delete, name="repair_delete"),
    path("repairs/<int:pk>/receive/", views.repair_receive, name="repair_receive"),
]
