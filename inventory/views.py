from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .forms import (
    AMJLoginForm, ProductForm, CategoryForm, SaleForm,
    RepairRecordForm, RepairDetailsEditForm, ReceiveRepairForm, ShopSettingsForm,
)
from .models import Product, Sale, RepairRecord, ShopSettings


def _product_price_map():
    return {str(pid): str(price) for pid, price in Product.objects.values_list("id", "sale_price")}


def _update_stock(product_id, qty_change):
    """Helper: update product stock by qty_change (negative to reduce)."""
    product = Product.objects.select_for_update().get(pk=product_id)
    product.quantity = F("quantity") + qty_change
    product.save(update_fields=["quantity"])
    return product


def _handle_inventory_form(request, form_class, model, template, success_msg, title="", **kwargs):
    """Generic view handler for CRUD forms."""
    if request.method == "POST":
        form = form_class(request.POST, request.FILES if form_class in [ProductForm, ShopSettingsForm] else None, **kwargs)
        if form.is_valid():
            form.save()
            messages.success(request, success_msg)
            return redirect(kwargs.get("next_url", f"inventory:{model.__name__.lower()}_list"))
    else:
        form = form_class(**kwargs)
    return render(request, template, {"form": form, "title": title})


class AMJLoginView(LoginView):
    template_name = "inventory/login.html"
    authentication_form = AMJLoginForm
    redirect_authenticated_user = True
    def form_valid(self, form):
        messages.success(self.request, f"Welcome back, {form.get_user().get_username()}!")
        return super().form_valid(form)


@login_required
def logout_view(request):
    auth_logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("inventory:login")


@login_required
def dashboard(request):
    tz = timezone
    products = Product.objects.all()
    
    stock_value = products.aggregate(v=Sum(ExpressionWrapper(F("quantity") * F("sale_price"), output_field=DecimalField())))["v"] or 0
    stock_cost_value = products.aggregate(v=Sum(ExpressionWrapper(F("quantity") * F("buy_price"), output_field=DecimalField())))["v"] or 0
    
    today = tz.localdate()
    month_start = today.replace(day=1)
    sales_this_month = Sale.objects.filter(sale_date__date__gte=month_start).select_related("product", "sold_by")
    
    profit = Decimal("0")
    for s in sales_this_month:
        profit += (s.total_amount or 0) - ((s.product.buy_price or 0) * s.quantity)
    
    active_repairs = RepairRecord.objects.filter(status="SENT").select_related("product", "created_by")
    
    return render(request, "inventory/dashboard.html", {
        "total_products": products.count(),
        "total_units": products.aggregate(s=Sum("quantity"))["s"] or 0,
        "stock_value": stock_value,
        "stock_cost_value": stock_cost_value,
        "recent_sales": Sale.objects.select_related("product", "sold_by")[:6],
        "revenue_this_month": sales_this_month.aggregate(s=Sum("total_amount"))["s"] or 0,
        "profit_this_month": profit,
        "sales_count_this_month": sales_this_month.count(),
        "active_repairs": active_repairs,
        "active_repairs_count": active_repairs.count(),
        "overdue_repairs_count": active_repairs.filter(expected_return_date__lt=today).count(),
    })


@login_required
def product_list(request):
    query = request.GET.get("q", "").strip()
    products = Product.objects.select_related("category").all()
    if query:
        products = products.filter(name__icontains=query) | products.filter(sku__icontains=query)
    return render(request, "inventory/product_list.html", {"products": products, "query": query})


@login_required
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, "inventory/product_detail.html", {
        "product": product,
        "sales": product.sales.all()[:20],
        "repairs": product.repairs.all()[:20],
    })


@login_required
def product_add(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.created_by = request.user
            product.save()
            messages.success(request, f"Product '{product.name}' added.")
            return redirect("inventory:product_list")
    else:
        form = ProductForm()
    return render(request, "inventory/product_form.html", {"form": form, "title": "Add Product"})


@login_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"Product '{product.name}' updated.")
            return redirect("inventory:product_list")
    else:
        form = ProductForm(instance=product)
    return render(request, "inventory/product_form.html", {"form": form, "title": "Edit Product", "product": product})


@login_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        name = product.name
        sales_count, repairs_count = product.sales.count(), product.repairs.count()
        product.delete()
        messages.success(request, f"Product '{name}' and {sales_count} sale(s) and {repairs_count} repair(s) deleted.")
        return redirect("inventory:product_list")
    return render(request, "inventory/product_confirm_delete.html", {
        "product": product,
        "sales_count": product.sales.count(),
        "repairs_count": product.repairs.count(),
    })


@login_required
def category_add(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Category added.")
            return redirect("inventory:product_add")
    else:
        form = CategoryForm()
    return render(request, "inventory/category_form.html", {"form": form})


@login_required
def sale_list(request):
    return render(request, "inventory/sale_list.html", {"sales": Sale.objects.select_related("product", "sold_by").all()})


@login_required
@transaction.atomic
def sale_add(request):
    if request.method == "POST":
        form = SaleForm(request.POST)
        if form.is_valid():
            sale = form.save(commit=False)
            product = Product.objects.select_for_update().get(pk=sale.product.pk)
            if sale.quantity > product.quantity:
                form.add_error("quantity", "Not enough stock available.")
            else:
                _update_stock(product.id, -sale.quantity)
                sale.sold_by = request.user
                sale.save()
                messages.success(request, f"Sale recorded: {sale.quantity} x {sale.product.name} for Rs {sale.total_amount}.")
                return redirect("inventory:sale_list")
    else:
        form = SaleForm()
    return render(request, "inventory/sale_form.html", {"form": form, "title": "Record a Sale", "product_price_map": _product_price_map()})


@login_required
@transaction.atomic
def sale_edit(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    orig_product_id, orig_qty = sale.product_id, sale.quantity
    
    if request.method == "POST":
        form = SaleForm(request.POST, instance=sale)
        if form.is_valid():
            _update_stock(orig_product_id, orig_qty)
            updated = form.save(commit=False)
            prod = Product.objects.select_for_update().get(pk=updated.product_id)
            if updated.quantity > prod.quantity:
                _update_stock(orig_product_id, -orig_qty)
                form.add_error("quantity", "Not enough stock available.")
            else:
                _update_stock(updated.product_id, -updated.quantity)
                updated.save()
                messages.success(request, "Sale updated.")
                return redirect("inventory:sale_list")
    else:
        form = SaleForm(instance=sale)
    return render(request, "inventory/sale_form.html", {"form": form, "title": "Edit Sale", "sale": sale, "product_price_map": _product_price_map()})


@login_required
@transaction.atomic
def sale_delete(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    if request.method == "POST":
        _update_stock(sale.product_id, sale.quantity)
        name, qty = sale.product.name, sale.quantity
        sale.delete()
        messages.success(request, f"Sale of {qty} x {name} deleted and stock restored.")
        return redirect("inventory:sale_list")
    return render(request, "inventory/sale_confirm_delete.html", {"sale": sale})


@login_required
def sale_receipt(request, pk):
    sale = get_object_or_404(Sale.objects.select_related("product", "sold_by"), pk=pk)
    return render(request, "inventory/sale_receipt.html", {"sale": sale})


@login_required
def shop_settings_view(request):
    shop = ShopSettings.load()
    if request.method == "POST":
        form = ShopSettingsForm(request.POST, request.FILES, instance=shop)
        if form.is_valid():
            form.save()
            messages.success(request, "Shop details updated.")
            return redirect("inventory:shop_settings")
    else:
        form = ShopSettingsForm(instance=shop)
    return render(request, "inventory/shop_settings_form.html", {"form": form, "shop": shop})


@login_required
def repair_list(request):
    status = request.GET.get("status", "")
    repairs = RepairRecord.objects.select_related("product").all()
    if status:
        repairs = repairs.filter(status=status)
    return render(request, "inventory/repair_list.html", {"repairs": repairs, "status": status})


@login_required
@transaction.atomic
def repair_add(request):
    if request.method == "POST":
        form = RepairRecordForm(request.POST)
        if form.is_valid():
            repair = form.save(commit=False)
            product = Product.objects.select_for_update().get(pk=repair.product.pk)
            if repair.quantity > product.quantity:
                form.add_error("quantity", "Not enough stock available to send for repair.")
            else:
                _update_stock(product.id, -repair.quantity)
                repair.created_by = request.user
                repair.status = "SENT"
                repair.save()
                messages.success(request, f"{repair.quantity} x {repair.product.name} sent to {repair.sent_to}.")
                return redirect("inventory:repair_list")
    else:
        form = RepairRecordForm()
    return render(request, "inventory/repair_form.html", {"form": form, "title": "Send Item for Repair"})


@login_required
@transaction.atomic
def repair_edit(request, pk):
    repair = get_object_or_404(RepairRecord, pk=pk)
    orig_product_id, orig_qty, orig_status = repair.product_id, repair.quantity, repair.status
    
    if orig_status == "SENT":
        if request.method == "POST":
            form = RepairRecordForm(request.POST, instance=repair)
            if form.is_valid():
                _update_stock(orig_product_id, orig_qty)
                updated = form.save(commit=False)
                prod = Product.objects.select_for_update().get(pk=updated.product_id)
                if updated.quantity > prod.quantity:
                    _update_stock(orig_product_id, -orig_qty)
                    form.add_error("quantity", "Not enough stock available.")
                else:
                    _update_stock(updated.product_id, -updated.quantity)
                    updated.save()
                    messages.success(request, "Repair record updated.")
                    return redirect("inventory:repair_list")
        else:
            form = RepairRecordForm(instance=repair)
        template = "inventory/repair_form.html"
    else:
        if request.method == "POST":
            form = RepairDetailsEditForm(request.POST, instance=repair)
            if form.is_valid():
                form.save()
                messages.success(request, "Repair record updated.")
                return redirect("inventory:repair_list")
        else:
            form = RepairDetailsEditForm(instance=repair)
        template = "inventory/repair_details_edit_form.html"
    
    return render(request, template, {"form": form, "title": "Edit Repair Record", "repair": repair})


@login_required
@transaction.atomic
def repair_delete(request, pk):
    repair = get_object_or_404(RepairRecord, pk=pk)
    if request.method == "POST":
        if repair.status == "SENT":
            _update_stock(repair.product_id, repair.quantity)
        name, qty, status = repair.product.name, repair.quantity, repair.status
        repair.delete()
        msg = f"Repair {qty}x{name} deleted and stock restored." if status == "SENT" else f"Repair {qty}x{name} deleted."
        messages.success(request, msg)
        return redirect("inventory:repair_list")
    return render(request, "inventory/repair_confirm_delete.html", {"repair": repair})


@login_required
@transaction.atomic
def repair_receive(request, pk):
    repair = get_object_or_404(RepairRecord, pk=pk, status="SENT")
    if request.method == "POST":
        form = ReceiveRepairForm(request.POST, instance=repair)
        if form.is_valid():
            repair = form.save(commit=False)
            repair.received_date = repair.received_date or timezone.localdate()
            repair.status = "RECEIVED"
            repair.save()
            _update_stock(repair.product_id, repair.quantity)
            messages.success(request, f"{repair.quantity} x {repair.product.name} received from {repair.sent_to}.")
            return redirect("inventory:repair_list")
    else:
        form = ReceiveRepairForm(instance=repair, initial={"received_date": timezone.localdate()})
    return render(request, "inventory/repair_receive_form.html", {"form": form, "repair": repair})



# ---------------------------------------------------------------------------
# Authentication — only authorized (pre-created) users can log in.
# There is intentionally NO public sign-up view. Accounts are created by an
# admin via /admin or `python manage.py createsuperuser`.
# ---------------------------------------------------------------------------

class AMJLoginView(LoginView):
    template_name = "inventory/login.html"
    authentication_form = AMJLoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(
            self.request,
            f"Welcome back, {form.get_user().get_username()}!"
        )
        return super().form_valid(form)


@login_required
def logout_view(request):
    auth_logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("inventory:login")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    from django.utils import timezone as tz
    
    products = Product.objects.all()
    total_products = products.count()
    total_units = products.aggregate(s=Sum("quantity"))["s"] or 0
    stock_value = products.aggregate(
        v=Sum(ExpressionWrapper(F("quantity") * F("sale_price"), output_field=DecimalField()))
    )["v"] or 0
    stock_cost_value = products.aggregate(
        v=Sum(ExpressionWrapper(F("quantity") * F("buy_price"), output_field=DecimalField()))
    )["v"] or 0

    recent_sales = Sale.objects.select_related("product", "sold_by")[:6]
    today = tz.localdate()
    month_start = today.replace(day=1)
    sales_this_month = Sale.objects.filter(
        sale_date__date__gte=month_start
    ).select_related("product", "sold_by")
    revenue_this_month = sales_this_month.aggregate(s=Sum("total_amount"))["s"] or 0

    # Calculate profit: total_amount - (quantity * buy_price)
    profit_this_month = Decimal("0")
    for s in sales_this_month:
        cost = (s.product.buy_price or Decimal("0")) * s.quantity
        profit_this_month += (s.total_amount or Decimal("0")) - cost

    active_repairs = RepairRecord.objects.filter(
        status=RepairRecord.STATUS_SENT
    ).select_related("product", "created_by")
    today_date = tz.localdate()
    overdue_repairs = active_repairs.filter(expected_return_date__lt=today_date)

    context = {
        "total_products": total_products,
        "total_units": total_units,
        "stock_value": stock_value,
        "stock_cost_value": stock_cost_value,
        "recent_sales": recent_sales,
        "revenue_this_month": revenue_this_month,
        "profit_this_month": profit_this_month,
        "sales_count_this_month": sales_this_month.count(),
        "active_repairs": active_repairs,
        "active_repairs_count": active_repairs.count(),
        "overdue_repairs_count": overdue_repairs.count(),
    }
    return render(request, "inventory/dashboard.html", context)


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

@login_required
def product_list(request):
    query = request.GET.get("q", "").strip()
    products = Product.objects.select_related("category").all()
    if query:
        products = products.filter(name__icontains=query) | products.filter(sku__icontains=query)
    return render(request, "inventory/product_list.html", {"products": products, "query": query})


@login_required
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    sales = product.sales.all()[:20]
    repairs = product.repairs.all()[:20]
    return render(request, "inventory/product_detail.html", {
        "product": product, "sales": sales, "repairs": repairs,
    })


@login_required
def product_add(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.created_by = request.user
            product.save()
            messages.success(request, f"Product '{product.name}' added to inventory.")
            return redirect("inventory:product_list")
    else:
        form = ProductForm()
    return render(request, "inventory/product_form.html", {"form": form, "title": "Add Product"})


@login_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"Product '{product.name}' updated.")
            return redirect("inventory:product_list")
    else:
        form = ProductForm(instance=product)
    return render(request, "inventory/product_form.html", {"form": form, "title": "Edit Product", "product": product})


@login_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    sales_count = product.sales.count()
    repairs_count = product.repairs.count()

    if request.method == "POST":
        name = product.name
        product.delete()  # CASCADE also removes all linked sales & repair records
        messages.success(
            request,
            f"Product '{name}' and all its related sale ({sales_count}) and repair "
            f"({repairs_count}) records have been permanently deleted."
        )
        return redirect("inventory:product_list")

    return render(request, "inventory/product_confirm_delete.html", {
        "product": product, "sales_count": sales_count, "repairs_count": repairs_count,
    })


@login_required
def category_add(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Category added.")
            return redirect("inventory:product_add")
    else:
        form = CategoryForm()
    return render(request, "inventory/category_form.html", {"form": form})


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------

@login_required
def sale_list(request):
    sales = Sale.objects.select_related("product", "sold_by").all()
    return render(request, "inventory/sale_list.html", {"sales": sales})


@login_required
@transaction.atomic
def sale_add(request):
    if request.method == "POST":
        form = SaleForm(request.POST)
        if form.is_valid():
            sale = form.save(commit=False)
            product = Product.objects.select_for_update().get(pk=sale.product.pk)
            if sale.quantity > product.quantity:
                form.add_error("quantity", "Not enough stock available.")
            else:
                product.quantity = F("quantity") - sale.quantity
                product.save(update_fields=["quantity"])
                sale.sold_by = request.user
                sale.save()
                messages.success(
                    request,
                    f"Sale recorded: {sale.quantity} x {sale.product.name} to {sale.customer_name} "
                    f"for Rs {sale.total_amount}. Inventory updated."
                )
                return redirect("inventory:sale_list")
    else:
        form = SaleForm()
    return render(request, "inventory/sale_form.html", {
        "form": form, "title": "Record a Sale", "product_price_map": _product_price_map(),
    })


@login_required
@transaction.atomic
def sale_edit(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    # IMPORTANT: capture the ORIGINAL quantity/product before binding the
    # form. Django's ModelForm mutates `sale` in place as soon as it's
    # validated (via instance=sale), so reading sale.quantity *after*
    # form.is_valid() would already reflect the new, edited value.
    original_product_id = sale.product_id
    original_quantity = sale.quantity

    if request.method == "POST":
        form = SaleForm(request.POST, instance=sale)
        if form.is_valid():
            original_product = Product.objects.select_for_update().get(pk=original_product_id)
            original_product.quantity = F("quantity") + original_quantity
            original_product.save(update_fields=["quantity"])

            updated_sale = form.save(commit=False)
            new_product = Product.objects.select_for_update().get(pk=updated_sale.product_id)

            if updated_sale.quantity > new_product.quantity:
                # Roll the revert back before re-showing the form with errors.
                original_product.quantity = F("quantity") - original_quantity
                original_product.save(update_fields=["quantity"])
                form.add_error("quantity", "Not enough stock available.")
            else:
                new_product.quantity = F("quantity") - updated_sale.quantity
                new_product.save(update_fields=["quantity"])
                updated_sale.save()
                messages.success(
                    request,
                    f"Sale updated: {updated_sale.quantity} x {updated_sale.product.name} "
                    f"for Rs {updated_sale.total_amount}. Inventory adjusted accordingly."
                )
                return redirect("inventory:sale_list")
    else:
        form = SaleForm(instance=sale)
    return render(request, "inventory/sale_form.html", {
        "form": form, "title": "Edit Sale", "sale": sale, "product_price_map": _product_price_map(),
    })


@login_required
@transaction.atomic
def sale_delete(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    if request.method == "POST":
        product = Product.objects.select_for_update().get(pk=sale.product_id)
        product.quantity = F("quantity") + sale.quantity
        product.save(update_fields=["quantity"])
        name, qty = sale.product.name, sale.quantity
        sale.delete()
        messages.success(request, f"Sale of {qty} x {name} deleted and stock restored.")
        return redirect("inventory:sale_list")
    return render(request, "inventory/sale_confirm_delete.html", {"sale": sale})


@login_required
def sale_receipt(request, pk):
    sale = get_object_or_404(Sale.objects.select_related("product", "sold_by"), pk=pk)
    return render(request, "inventory/sale_receipt.html", {"sale": sale})


@login_required
def shop_settings_view(request):
    shop = ShopSettings.load()
    if request.method == "POST":
        form = ShopSettingsForm(request.POST, request.FILES, instance=shop)
        if form.is_valid():
            form.save()
            messages.success(request, "Shop details updated. New receipts will use this branding.")
            return redirect("inventory:shop_settings")
    else:
        form = ShopSettingsForm(instance=shop)
    return render(request, "inventory/shop_settings_form.html", {"form": form, "shop": shop})


# ---------------------------------------------------------------------------
# Repairs
# ---------------------------------------------------------------------------

@login_required
def repair_list(request):
    status = request.GET.get("status", "")
    repairs = RepairRecord.objects.select_related("product").all()
    if status:
        repairs = repairs.filter(status=status)
    return render(request, "inventory/repair_list.html", {"repairs": repairs, "status": status})


@login_required
@transaction.atomic
def repair_add(request):
    if request.method == "POST":
        form = RepairRecordForm(request.POST)
        if form.is_valid():
            repair = form.save(commit=False)
            product = Product.objects.select_for_update().get(pk=repair.product.pk)
            if repair.quantity > product.quantity:
                form.add_error("quantity", "Not enough stock available to send for repair.")
            else:
                product.quantity = F("quantity") - repair.quantity
                product.save(update_fields=["quantity"])
                repair.created_by = request.user
                repair.status = RepairRecord.STATUS_SENT
                repair.save()
                messages.success(
                    request,
                    f"{repair.quantity} x {repair.product.name} marked as sent for repair to {repair.sent_to}. "
                    f"Inventory updated."
                )
                return redirect("inventory:repair_list")
    else:
        form = RepairRecordForm()
    return render(request, "inventory/repair_form.html", {"form": form, "title": "Send Item for Repair"})


@login_required
@transaction.atomic
def repair_edit(request, pk):
    repair = get_object_or_404(RepairRecord, pk=pk)
    # Capture originals before any form binds to this instance (same
    # mutation hazard as sale_edit above).
    original_product_id = repair.product_id
    original_quantity = repair.quantity
    original_status = repair.status

    if original_status == RepairRecord.STATUS_SENT:
        # Product/quantity are still editable — that stock is currently
        # "out" of sellable inventory, so we revert-then-reapply.
        if request.method == "POST":
            form = RepairRecordForm(request.POST, instance=repair)
            if form.is_valid():
                original_product = Product.objects.select_for_update().get(pk=original_product_id)
                original_product.quantity = F("quantity") + original_quantity
                original_product.save(update_fields=["quantity"])

                updated_repair = form.save(commit=False)
                new_product = Product.objects.select_for_update().get(pk=updated_repair.product_id)

                if updated_repair.quantity > new_product.quantity:
                    original_product.quantity = F("quantity") - original_quantity
                    original_product.save(update_fields=["quantity"])
                    form.add_error("quantity", "Not enough stock available to send for repair.")
                else:
                    new_product.quantity = F("quantity") - updated_repair.quantity
                    new_product.save(update_fields=["quantity"])
                    updated_repair.save()
                    messages.success(request, "Repair record updated. Inventory adjusted accordingly.")
                    return redirect("inventory:repair_list")
        else:
            form = RepairRecordForm(instance=repair)
        template = "inventory/repair_form.html"
    else:
        # Already received: that stock is back on the shelf, so product and
        # quantity are locked to avoid double-counting; only details editable.
        if request.method == "POST":
            form = RepairDetailsEditForm(request.POST, instance=repair)
            if form.is_valid():
                form.save()
                messages.success(request, "Repair record updated.")
                return redirect("inventory:repair_list")
        else:
            form = RepairDetailsEditForm(instance=repair)
        template = "inventory/repair_details_edit_form.html"

    return render(request, template, {"form": form, "title": "Edit Repair Record", "repair": repair})


@login_required
@transaction.atomic
def repair_delete(request, pk):
    repair = get_object_or_404(RepairRecord, pk=pk)
    if request.method == "POST":
        # If it was still out for repair, that quantity is currently
        # deducted from stock — restore it before deleting the record.
        if repair.status == RepairRecord.STATUS_SENT:
            product = Product.objects.select_for_update().get(pk=repair.product_id)
            product.quantity = F("quantity") + repair.quantity
            product.save(update_fields=["quantity"])
        name, qty, status = repair.product.name, repair.quantity, repair.status
        repair.delete()
        if status == RepairRecord.STATUS_SENT:
            messages.success(request, f"Repair record for {qty} x {name} deleted and stock restored.")
        else:
            messages.success(request, f"Repair record for {qty} x {name} deleted.")
        return redirect("inventory:repair_list")
    return render(request, "inventory/repair_confirm_delete.html", {"repair": repair})


@login_required
@transaction.atomic
def repair_receive(request, pk):
    repair = get_object_or_404(RepairRecord, pk=pk, status=RepairRecord.STATUS_SENT)
    if request.method == "POST":
        form = ReceiveRepairForm(request.POST, instance=repair)
        if form.is_valid():
            repair = form.save(commit=False)
            if not repair.received_date:
                repair.received_date = timezone.localdate()
            repair.status = RepairRecord.STATUS_RECEIVED
            repair.save()

            product = Product.objects.select_for_update().get(pk=repair.product.pk)
            product.quantity = F("quantity") + repair.quantity
            product.save(update_fields=["quantity"])

            messages.success(
                request,
                f"{repair.quantity} x {repair.product.name} received back from {repair.sent_to}. "
                f"Inventory updated."
            )
            return redirect("inventory:repair_list")
    else:
        form = ReceiveRepairForm(instance=repair, initial={"received_date": timezone.localdate()})
    return render(request, "inventory/repair_receive_form.html", {"form": form, "repair": repair})
