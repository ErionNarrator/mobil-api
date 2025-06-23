from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import CustomUser, Currency, UserAccount, Transaction


class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('username', 'email')
    ordering = ('username',)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('email',)}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
    )


class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'symbol', 'exchange_rate', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')


class UserAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'account_number', 'phone_number', 'balance', 'default_currency', 'is_active')
    list_filter = ('is_active', 'default_currency')
    search_fields = ('user__username', 'user__email', 'account_number', 'phone_number')
    readonly_fields = ('account_number', 'balance', 'created_at', 'updated_at')


class TransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'sender', 'recipient', 'amount',
                   'currency', 'transaction_type', 'timestamp', 'is_successful')
    list_filter = ('transaction_type', 'currency', 'is_successful', 'timestamp')
    search_fields = ('transaction_id', 'sender__user__username', 'recipient__user__username', 
                    'description')
    readonly_fields = ('transaction_id', 'sender', 'recipient', 'amount', 
                      'currency', 'transaction_type', 'timestamp', 'is_successful')
    date_hierarchy = 'timestamp'


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Currency, CurrencyAdmin)
admin.site.register(UserAccount, UserAccountAdmin)
admin.site.register(Transaction, TransactionAdmin)
