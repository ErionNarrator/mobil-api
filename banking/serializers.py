from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.tokens import RefreshToken
from .models import UserAccount, Currency, Transaction, CustomUser
from decimal import Decimal


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User registration and profile information"""
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        validators=[validate_password]
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    phone_number = serializers.CharField(
        write_only=True,
        required=True,
        max_length=17
    )

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'password', 'password2', 'phone_number']
        extra_kwargs = {
            'email': {'required': True}
        }

    def validate(self, data):
        # Check if passwords match
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password": "Password fields did not match."})
        return data

    def create(self, validated_data):
        # Remove password2 and phone_number from the data used to create User
        phone_number = validated_data.pop('phone_number')
        validated_data.pop('password2')

        # Create the CustomUser instance
        user = CustomUser.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )

        # Update the phone number in UserAccount
        # UserAccount is automatically created via signal, so we just update it
        user.account.phone_number = phone_number
        user.account.save()

        return user


class CurrencySerializer(serializers.ModelSerializer):
    """Serializer for Currency model"""

    class Meta:
        model = Currency
        fields = ['code', 'name', 'symbol', 'exchange_rate', 'is_active']
        read_only_fields = ['code']  # Currency code cannot be changed


class UserAccountSerializer(serializers.ModelSerializer):
    """Serializer for UserAccount model"""
    user = UserSerializer(read_only=True)
    default_currency = CurrencySerializer(read_only=True)
    default_currency_code = serializers.CharField(write_only=True, required=False)
    balance_in_usd = serializers.SerializerMethodField()
    balance_in_eur = serializers.SerializerMethodField()
    balance_in_rub = serializers.SerializerMethodField()

    class Meta:
        model = UserAccount
        fields = [
            'id', 'user', 'phone_number', 'balance', 'account_number',
            'default_currency', 'default_currency_code', 'created_at',
            'updated_at', 'is_active', 'balance_in_usd', 'balance_in_eur', 'balance_in_rub'
        ]
        read_only_fields = [
            'id', 'user', 'balance', 'account_number', 'created_at',
            'updated_at', 'balance_in_usd', 'balance_in_eur', 'balance_in_rub'
        ]

    def get_balance_in_usd(self, obj):
        return float(obj.get_balance_in_currency('USD'))

    def get_balance_in_eur(self, obj):
        return float(obj.get_balance_in_currency('EUR'))

    def get_balance_in_rub(self, obj):
        return float(obj.get_balance_in_currency('RUB'))

    def update(self, instance, validated_data):
        # Handle currency change if provided
        if 'default_currency_code' in validated_data:
            currency_code = validated_data.pop('default_currency_code')
            try:
                currency = Currency.objects.get(code=currency_code)
                instance.default_currency = currency
            except Currency.DoesNotExist:
                raise serializers.ValidationError({"default_currency_code": "Currency not found"})

        return super().update(instance, validated_data)


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for Transaction model"""
    sender_username = serializers.SerializerMethodField()
    recipient_username = serializers.SerializerMethodField()
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    currency_symbol = serializers.CharField(source='currency.symbol', read_only=True)

    # Fields for creating a transaction
    recipient_id = serializers.IntegerField(write_only=True, required=False)
    recipient_phone = serializers.CharField(write_only=True, required=False)
    currency_id = serializers.CharField(write_only=True)

    class Meta:
        model = Transaction
        fields = [
            'transaction_id', 'sender', 'recipient', 'sender_username',
            'recipient_username', 'amount', 'currency_code', 'currency_symbol',
            'transaction_type', 'description', 'timestamp', 'is_successful',
            'recipient_id', 'recipient_phone', 'currency_id'
        ]
        read_only_fields = [
            'transaction_id', 'sender', 'recipient', 'sender_username',
            'recipient_username', 'currency_code', 'currency_symbol',
            'transaction_type', 'timestamp', 'is_successful'
        ]

    def get_sender_username(self, obj):
        if obj.sender:
            return obj.sender.user.username
        return None

    def get_recipient_username(self, obj):
        if obj.recipient:
            return obj.recipient.user.username
        return None

    def validate(self, data):
        recipient_id = data.get('recipient_id')
        recipient_phone = data.get('recipient_phone')

        # Either recipient ID or phone must be provided
        if not recipient_id and not recipient_phone:
            raise serializers.ValidationError({
                "recipient": "Either recipient_id or recipient_phone must be provided"
            })

        # Amount must be positive
        if data.get('amount', 0) <= 0:
            raise serializers.ValidationError({
                "amount": "Amount must be positive"
            })

        return data

    def create(self, validated_data):
        # Get the sender (current user's account)
        sender = self.context['request'].user.account

        # Find recipient by ID or phone number
        recipient = None
        if 'recipient_id' in validated_data:
            try:
                recipient = UserAccount.objects.get(id=validated_data.pop('recipient_id'))
            except UserAccount.DoesNotExist:
                raise serializers.ValidationError({"recipient_id": "Recipient account not found"})
        else:
            try:
                recipient = UserAccount.objects.get(phone_number=validated_data.pop('recipient_phone'))
            except UserAccount.DoesNotExist:
                raise serializers.ValidationError({"recipient_phone": "Recipient with this phone number not found"})

        # Get currency
        try:
            currency = Currency.objects.get(code=validated_data.pop('currency_id'))
        except Currency.DoesNotExist:
            raise serializers.ValidationError({"currency_id": "Currency not found"})

        amount = Decimal(validated_data.pop('amount'))
        description = validated_data.pop('description', '')

        # Execute the transfer
        try:
            transaction = Transaction.transfer(
                sender=sender,
                recipient=recipient,
                amount=amount,
                currency=currency,
                description=description
            )
            return transaction
        except ValueError as e:
            raise serializers.ValidationError({"non_field_errors": str(e)})


class TransactionListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing transactions"""
    sender_username = serializers.SerializerMethodField()
    recipient_username = serializers.SerializerMethodField()
    currency_code = serializers.CharField(source='currency.code')

    class Meta:
        model = Transaction
        fields = [
            'transaction_id', 'sender_username', 'recipient_username',
            'amount', 'currency_code', 'transaction_type',
            'description', 'timestamp', 'is_successful'
        ]

    def get_sender_username(self, obj):
        if obj.sender:
            return obj.sender.user.username
        return None

    def get_recipient_username(self, obj):
        if obj.recipient:
            return obj.recipient.user.username
        return None


class ProfileLoginSerializer(serializers.Serializer):
    """Serializer for profile login that returns JWT tokens and user details"""
    username = serializers.CharField()
    password = serializers.CharField(style={'input_type': 'password'})
    
    # Read-only fields for response
    access_token = serializers.CharField(read_only=True)
    refresh_token = serializers.CharField(read_only=True)
    user_profile = UserAccountSerializer(read_only=True)
    
    def validate(self, data):
        username = data.get('username')
        password = data.get('password')
        
        if username and password:
            user = authenticate(username=username, password=password)
            
            if user:
                if not user.is_active:
                    raise serializers.ValidationError('User account is disabled.')
                
                # Generate JWT tokens
                refresh = RefreshToken.for_user(user)
                
                data['user'] = user
                data['access_token'] = str(refresh.access_token)
                data['refresh_token'] = str(refresh)
                data['user_profile'] = user.account
                
                return data
            else:
                raise serializers.ValidationError('Unable to login with provided credentials.')
        else:
            raise serializers.ValidationError('Must include username and password.')
