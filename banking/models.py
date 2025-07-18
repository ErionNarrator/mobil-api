from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.core.validators import RegexValidator, MinValueValidator
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from decimal import Decimal
import uuid


class CustomUserManager(BaseUserManager):

    def create_user(self, username, email, password=None, **extra_fields):

        if not username:
            raise ValueError(_('The Username field must be set'))
        if not email:
            raise ValueError(_('The Email field must be set'))
        
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):

        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        
        return self.create_user(username, email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):

    username = models.CharField(
        max_length=155,
        unique=True,
        verbose_name=_("Username")
    )
    email = models.EmailField(
        max_length=255,
        unique=True,
        verbose_name=_("Email Address")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active Status")
    )
    is_staff = models.BooleanField(
        default=False,
        verbose_name=_("Staff Status")
    )
    date_joined = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("Date Joined")
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'username'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = ['email']

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    def __str__(self):
        return self.username

    def get_full_name(self):

        return self.username


    def get_short_name(self):
        return self.username

class Currency(models.Model):
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('RUB', 'Russian Ruble'),
    ]

    code = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        unique=True,
        primary_key=True,
        verbose_name=_("Currency Code")
    )
    name = models.CharField(max_length=32, verbose_name=_("Currency Name"))
    symbol = models.CharField(max_length=5, verbose_name=_("Currency Symbol"))
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=1.0,
        verbose_name=_("Exchange Rate to USD")
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Active Status"))

    class Meta:
        verbose_name = _("Currency")
        verbose_name_plural = _("Currencies")

    def __str__(self):
        return f"{self.code} ({self.name})"

    def convert_to(self, amount, target_currency):

        if self.code == target_currency.code:
            return amount

        amount_in_usd = amount / self.exchange_rate

        return amount_in_usd * target_currency.exchange_rate


class UserAccount(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='account',
        verbose_name=_("User")
    )
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message=_("Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
    )
    phone_number = models.CharField(
        validators=[phone_regex],
        max_length=18,
        unique=True,
        verbose_name=_("Phone Number")
    )
    default_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        default='USD',
        verbose_name=_("Default Currency")
    )
    account_number = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        verbose_name=_("Account Number")
    )
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Balance")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active Status"))

    class Meta:
        verbose_name = _("User Account")
        verbose_name_plural = _("User Accounts")

    def __str__(self):
        return f"{self.user.username}'s Account ({self.account_number})"

    def save(self, *args, **kwargs):
        if not self.account_number:
            self.account_number = f"ACC{uuid.uuid4().hex[:16].upper()}"
        super().save(*args, **kwargs)

    def has_sufficient_balance(self, amount):
        return self.balance >= amount

    def deposit(self, amount):
        if amount <= 0:
            raise ValueError(_("Deposit amount must be positive"))

        self.balance += Decimal(amount)
        self.save(update_fields=['balance', 'updated_at'])

        return self.balance

    def withdraw(self, amount):
        amount = Decimal(amount)

        if amount <= 0:
            raise ValueError(_("Withdrawal amount must be positive"))

        if not self.has_sufficient_balance(amount):
            raise ValueError(_("Insufficient funds"))

        self.balance -= amount
        self.save(update_fields=['balance', 'updated_at'])

        return self.balance

    def get_balance_in_currency(self, currency_code):
        if currency_code == self.default_currency.code:
            return self.balance

        try:
            target_currency = Currency.objects.get(code=currency_code)
            return self.default_currency.convert_to(self.balance, target_currency)
        except Currency.DoesNotExist:
            return Decimal('0.00')

class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('TRANSFER', 'Transfer'),
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('CURRENCY_EXCHANGE', 'Currency Exchange'),
    ]

    transaction_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("Transaction ID")
    )
    sender = models.ForeignKey(
        UserAccount,
        on_delete=models.PROTECT,
        related_name='sent_transactions',
        null=True,
        blank=True,
        verbose_name=_("Sender")
    )
    recipient = models.ForeignKey(
        UserAccount,
        on_delete=models.PROTECT,
        related_name='received_transactions',
        null=True,
        blank=True,
        verbose_name=_("Recipient")
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_("Amount")
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        verbose_name=_("Currency")
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES,
        verbose_name=_("Transaction Type")
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Description")
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Timestamp")
    )
    is_successful = models.BooleanField(
        default=False,
        verbose_name=_("Success Status")
    )

    class Meta:
        verbose_name = _("Transaction")
        verbose_name_plural = _("Transactions")
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.transaction_id} - {self.amount} {self.currency.code}"

    @classmethod
    def transfer(cls, sender, recipient, amount, currency, description=""):

        if sender == recipient:
            raise ValueError(_("Cannot transfer to the same account"))

        if not sender.has_sufficient_balance(amount):
            raise ValueError(_("Insufficient funds for transfer"))

        transaction = cls.objects.create(
            sender=sender,
            recipient=recipient,
            amount=amount,
            currency=currency,
            transaction_type='TRANSFER',
            description=description,
            is_successful=False

        )

        try:
            sender.withdraw(amount)
            recipient.deposit(amount)

            transaction.is_successful = True
            transaction.save(update_fields=['is_successful'])

        except Exception as e:

            raise e

        return transaction


@receiver(post_save, sender=CustomUser)
def create_user_account(sender, instance, created, **kwargs):
    if created:
        default_currency, _ = Currency.objects.get_or_create(
            code='USD',
            defaults={
                'name': 'US Dollar',
                'symbol': '$',
                'exchange_rate': 1.0
            }
        )

        UserAccount.objects.create(
            user=instance,
            default_currency=default_currency,
            phone_number=f"+1{uuid.uuid4().hex[:10]}"  # Placeholder phone number
        )
