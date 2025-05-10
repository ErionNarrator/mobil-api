from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator, MinValueValidator
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
import uuid


class Currency(models.Model):
    """Model to represent supported currencies and their exchange rates"""
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
    # Rate relative to USD (1 USD = X of this currency)
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
        """
        Convert an amount from this currency to the target currency

        Args:
            amount (Decimal): The amount to convert
            target_currency (Currency): The currency to convert to

        Returns:
            Decimal: The converted amount
        """
        if self.code == target_currency.code:
            return amount

        # Convert to USD first (as base currency)
        amount_in_usd = amount / self.exchange_rate

        # Then convert from USD to target currency
        return amount_in_usd * target_currency.exchange_rate


class UserAccount(models.Model):
    """Model to extend User with additional banking information"""
    user = models.OneToOneField(
        User,
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
        max_length=17,
        unique=True,
        verbose_name=_("Phone Number")
    )
    card_number_regex = RegexValidator(
        regex=r'^(\d{4}[-\s]?){3}\d{4}$|^\d{16}$',
        message=_("Card number must be 16 digits, optionally grouped in 4 digits separated by spaces or hyphens.")
    )
    card_number = models.CharField(
        validators=[card_number_regex],
        max_length=19,  # 16 digits + 3 separators
        unique=True,
        null=True,
        blank=True,
        verbose_name=_("Bank Card Number")
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
            # Generate a unique account number if not already set
            self.account_number = f"ACC{uuid.uuid4().hex[:16].upper()}"
        super().save(*args, **kwargs)

    def has_sufficient_balance(self, amount):
        """Check if account has sufficient balance for a transaction"""
        return self.balance >= amount

    def deposit(self, amount):
        """Deposit funds to the account"""
        if amount <= 0:
            raise ValueError(_("Deposit amount must be positive"))

        self.balance += Decimal(amount)
        self.save(update_fields=['balance', 'updated_at'])

        return self.balance

    def withdraw(self, amount):
        """Withdraw funds from the account"""
        amount = Decimal(amount)

        if amount <= 0:
            raise ValueError(_("Withdrawal amount must be positive"))

        if not self.has_sufficient_balance(amount):
            raise ValueError(_("Insufficient funds"))

        self.balance -= amount
        self.save(update_fields=['balance', 'updated_at'])

        return self.balance

    def get_balance_in_currency(self, currency_code):
        """Get account balance converted to specified currency"""
        if currency_code == self.default_currency.code:
            return self.balance

        target_currency = Currency.objects.get(code=currency_code)
        return self.default_currency.convert_to(self.balance, target_currency)


class Transaction(models.Model):
    """Model to track money transfers and operations"""
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
        """
        Create and process a transfer between accounts

        Args:
            sender (UserAccount): The sending account
            recipient (UserAccount): The receiving account
            amount (Decimal): The amount to transfer
            currency (Currency): The currency of the transfer
            description (str, optional): Transaction description

        Returns:
            Transaction: The created transaction
        """
        if sender == recipient:
            raise ValueError(_("Cannot transfer to the same account"))

        if not sender.has_sufficient_balance(amount):
            raise ValueError(_("Insufficient funds for transfer"))

        # Create the transaction first (not marked successful yet)
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
            # Process the transfer
            sender.withdraw(amount)
            recipient.deposit(amount)

            # Mark as successful
            transaction.is_successful = True
            transaction.save(update_fields=['is_successful'])

        except Exception as e:
            # Transaction failed, don't update is_successful flag
            # Log the error here if needed
            raise e

        return transaction


# Automatically create UserAccount when a User is created
@receiver(post_save, sender=User)
def create_user_account(sender, instance, created, **kwargs):
    if created:
        # Get default currency (USD)
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