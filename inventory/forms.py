from decimal import Decimal
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import Product, Sale, RepairRecord, Category, ShopSettings


class StyledFormMixin:
    def _style_fields(self):
        for field in self.fields.values():
            css = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs["class"] = (field.widget.attrs.get("class", "") + f" {css}").strip()


class AMJLoginForm(StyledFormMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
        self.fields["username"].widget.attrs["placeholder"] = "Username"
        self.fields["password"].widget.attrs["placeholder"] = "Password"


class ProductForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "image", "category", "metal_type", "weight", "weight_unit", "quantity", "buy_price", "sale_price", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
        self.fields["category"].required = False
        self.fields["category"].empty_label = "-- Select category (optional) --"
        self.fields["weight"].required = False
    
    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            return name

        queryset = Product.objects.filter(name__iexact=name)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError("A product with this name already exists.")
        return name

    def clean(self):
        cleaned_data = super().clean()
        buy = cleaned_data.get("buy_price")
        sale = cleaned_data.get("sale_price")
        if buy and sale and sale < buy:
            self.add_error("sale_price", "Sale price is lower than the buy price — double check this is correct.")
        return cleaned_data


class CategoryForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class SaleForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Sale
        fields = ["product", "quantity", "unit_price", "discount", "customer_name", "customer_contact", "customer_address", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
        qs = Product.objects.filter(quantity__gt=0)
        if self.instance.pk:
            qs = qs | Product.objects.filter(pk=self.instance.product_id)
        self.fields["product"].queryset = qs.distinct()
        self.fields["discount"].required = False
        if not self.instance.pk:
            self.fields["unit_price"].widget.attrs["placeholder"] = "Auto-filled from product, editable"
    
    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get("product")
        qty = cleaned_data.get("quantity")
        price = cleaned_data.get("unit_price")
        discount = cleaned_data.get("discount") or Decimal("0")
        
        if product and qty:
            available = product.quantity + (self.instance.quantity if self.instance.pk and self.instance.product_id == product.id else 0)
            if qty > available:
                self.add_error("quantity", f"Only {available} unit(s) of '{product.name}' are available.")
        
        if price and qty and discount and discount > price * qty:
            self.add_error("discount", "Discount cannot exceed total sale amount.")
        
        return cleaned_data


class RepairRecordForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = RepairRecord
        fields = ["product", "quantity", "sent_to", "sent_to_contact", "issue_description", "sent_date", "expected_return_date", "repair_cost", "notes"]
        widgets = {
            "issue_description": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "sent_date": forms.DateInput(attrs={"type": "date"}),
            "expected_return_date": forms.DateInput(attrs={"type": "date"}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
    
    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get("product")
        qty = cleaned_data.get("quantity")
        if product and qty:
            available = product.quantity + (self.instance.quantity if self.instance.pk and self.instance.product_id == product.id else 0)
            if qty > available:
                self.add_error("quantity", f"Only {available} unit(s) of '{product.name}' are available to repair.")
        return cleaned_data


class RepairDetailsEditForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = RepairRecord
        fields = ["sent_to", "sent_to_contact", "issue_description", "sent_date", "expected_return_date", "received_date", "repair_cost", "notes"]
        widgets = {
            "issue_description": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "sent_date": forms.DateInput(attrs={"type": "date"}),
            "expected_return_date": forms.DateInput(attrs={"type": "date"}),
            "received_date": forms.DateInput(attrs={"type": "date"}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class ReceiveRepairForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = RepairRecord
        fields = ["received_date", "repair_cost", "notes"]
        widgets = {
            "received_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class ShopSettingsForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ShopSettings
        fields = ["shop_name", "tagline", "logo", "address", "phone", "email", "receipt_note"]
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
