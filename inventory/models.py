from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.urls import reverse


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]
    def __str__(self):
        return self.name


class Product(models.Model):
    METAL_CHOICES = [("GOLD", "Gold"), ("SILVER", "Silver"), ("OTHER", "Other")]
    WEIGHT_CHOICES = [("GRAM", "Grams"), ("TOLA", "Tola")]
    
    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    metal_type = models.CharField(max_length=10, choices=METAL_CHOICES, default="GOLD")
    weight = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)])
    weight_unit = models.CharField(max_length=6, choices=WEIGHT_CHOICES, default="GRAM")
    sku = models.CharField("SKU / Item Code", max_length=50, unique=True, blank=True)
    quantity = models.PositiveIntegerField(default=0)
    buy_price = models.DecimalField("Buy Price (Cost)", max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    sale_price = models.DecimalField("Sale Price", max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="products_added")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
    def __str__(self):
        return f"{self.name} ({self.sku})"
    
    def save(self, *args, **kwargs):
        if not self.sku:
            from .models import ShopSettings
            shop = ShopSettings.load()
            prefix = "".join([w[0].upper() for w in shop.shop_name.split()] or ["SKU"])
            last = Product.objects.order_by("-id").first()
            self.sku = f"{prefix}-{(last.id + 1 if last else 1):04d}"
        super().save(*args, **kwargs)
    
    @property
    def total_value(self):
        return self.quantity * self.sale_price
    
    @property
    def total_cost_value(self):
        return self.quantity * self.buy_price
    
    @property
    def profit_margin(self):
        return (self.sale_price - self.buy_price) if self.sale_price else 0
    
    @property
    def weight_display(self):
        if self.weight is None:
            return ""
        unit = "g" if self.weight_unit == "GRAM" else "tola"
        return f"{self.weight} {unit}"
    
    def get_absolute_url(self):
        return reverse("inventory:product_detail", args=[self.pk])


class Sale(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="sales")
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0, blank=True, validators=[MinValueValidator(0)])
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=0)
    customer_name = models.CharField(max_length=200)
    customer_contact = models.CharField(max_length=50, blank=True)
    customer_address = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    sold_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="sales_made")
    sale_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-sale_date"]
    def __str__(self):
        return f"{self.quantity} x {self.product.name} sold to {self.customer_name}"
    
    def compute_total(self):
        gross = (self.unit_price or 0) * self.quantity
        return max(0, gross - (self.discount or 0))
    
    @property
    def line_gross(self):
        return (self.unit_price or 0) * self.quantity
    
    def save(self, *args, **kwargs):
        self.total_amount = self.compute_total()
        super().save(*args, **kwargs)


class RepairRecord(models.Model):
    STATUS_SENT = "SENT"
    STATUS_RECEIVED = "RECEIVED"
    STATUS_CHOICES = [("SENT", "Out for Repair"), ("RECEIVED", "Received Back")]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="repairs")
    quantity = models.PositiveIntegerField(default=1)
    sent_to = models.CharField("Sent To (Karigar / Workshop)", max_length=200)
    sent_to_contact = models.CharField(max_length=50, blank=True)
    issue_description = models.TextField(blank=True)
    sent_date = models.DateField()
    expected_return_date = models.DateField(blank=True, null=True)
    received_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="SENT")
    repair_cost = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="repairs_logged")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["-sent_date"]
    def __str__(self):
        return f"{self.product.name} sent to {self.sent_to} ({self.get_status_display()})"
    
    @property
    def is_overdue(self):
        from django.utils import timezone
        return self.status == "SENT" and self.expected_return_date and timezone.localdate() > self.expected_return_date


class ShopSettings(models.Model):
    shop_name = models.CharField(max_length=200, default="My Shop")
    tagline = models.CharField(max_length=200, blank=True, default="Fine Gold & Silver Jewellery")
    logo = models.ImageField(upload_to="shop/", blank=True, null=True)
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    receipt_note = models.CharField(max_length=255, blank=True, default="Thank you for shopping with us!")
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Shop Settings"
    def __str__(self):
        return self.shop_name
    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        pass
    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]

