from django.shortcuts import render
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.views import APIView
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView, ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, timedelta
from decimal import Decimal
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import UserAccount, Currency, Transaction
from .serializers import (
    UserSerializer,
    UserAccountSerializer,
    CurrencySerializer,
    TransactionSerializer,
    TransactionListSerializer
)


class RegisterView(CreateAPIView):
    """View for user registration"""
    permission_classes = [AllowAny]
    serializer_class = UserSerializer

    @swagger_auto_schema(
        operation_summary="Register new user",
        operation_description="Create a new user account with email, password, and profile information",
        request_body=UserSerializer,
        responses={
            201: openapi.Response(
                description="Successfully registered",
                schema=UserSerializer
            ),
            400: openapi.Response(
                description="Bad Request",
                examples={
                    "application/json": {
                        "password": ["Password fields didn't match."],
                        "email": ["This field is required."]
                    }
                }
            )
        },
        tags=['authentication']
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class UserProfileView(RetrieveUpdateAPIView):
    """View for user profile management"""
    permission_classes = [IsAuthenticated]
    serializer_class = UserAccountSerializer

    @swagger_auto_schema(
        operation_summary="Get user profile",
        operation_description="Retrieve the authenticated user's profile information",
        responses={
            200: UserAccountSerializer,
            401: "Unauthorized"
        },
        tags=['profile']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Update user profile",
        operation_description="Update the authenticated user's profile information",
        request_body=UserAccountSerializer,
        responses={
            200: UserAccountSerializer,
            400: "Bad Request - Invalid data",
            401: "Unauthorized"
        },
        tags=['profile']
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Partially update user profile",
        operation_description="Partially update the authenticated user's profile information",
        request_body=UserAccountSerializer,
        responses={
            200: UserAccountSerializer,
            400: "Bad Request - Invalid data",
            401: "Unauthorized"
        },
        tags=['profile']
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    def get_object(self):
        """Return the logged-in user's account"""
        return self.request.user.account


class UserAccountViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing user accounts"""
    queryset = UserAccount.objects.all()
    serializer_class = UserAccountSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="List all accounts",
        operation_description="Returns a list of all user accounts",
        responses={
            200: UserAccountSerializer(many=True),
            401: "Unauthorized"
        },
        tags=['accounts']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Get account details",
        operation_description="Returns details of a specific account",
        responses={
            200: UserAccountSerializer,
            401: "Unauthorized",
            404: "Not found"
        },
        tags=['accounts']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="View own accounts",
        operation_description="Returns the authenticated user's account details",
        responses={
            200: UserAccountSerializer,
            401: "Unauthorized"
        },
        tags=['accounts']
    )
    @action(detail=False, methods=['get'])
    def my_accounts(self, request):
        """View own accounts"""
        user_account = request.user.account
        serializer = self.get_serializer(user_account)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_summary="Change account currency",
        operation_description="Change the default currency of the account",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['default_currency_code'],
            properties={
                'default_currency_code': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Currency code (USD, EUR, RUB)',
                    enum=['USD', 'EUR', 'RUB']
                )
            }
        ),
        responses={
            200: UserAccountSerializer,
            400: "Invalid currency code",
            401: "Unauthorized"
        },
        tags=['accounts']
    )
    @action(detail=False, methods=['post'])
    def change_currency(self, request):
        """Change default currency"""
        user_account = request.user.account
        serializer = self.get_serializer(user_account, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_summary="Deposit funds",
        operation_description="Add funds to the account (demo/testing only)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['amount'],
            properties={
                'amount': openapi.Schema(
                    type=openapi.TYPE_NUMBER,
                    description='Amount to deposit',
                    example=100.00
                ),
                'currency_code': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Currency code (defaults to USD)',
                    default='USD',
                    enum=['USD', 'EUR', 'RUB']
                )
            }
        ),
        responses={
            200: UserAccountSerializer,
            400: "Invalid amount or currency",
            401: "Unauthorized"
        },
        tags=['accounts']
    )
    @action(detail=False, methods=['post'])
    def deposit(self, request):
        """Add funds to account (for demo/testing only)"""
        user_account = request.user.account

        try:
            amount = Decimal(request.data.get('amount', 0))
            if amount <= 0:
                return Response(
                    {"error": "Amount must be positive"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get currency
            currency_code = request.data.get('currency_code', 'USD')
            try:
                currency = Currency.objects.get(code=currency_code)
            except Currency.DoesNotExist:
                return Response(
                    {"error": "Currency not found"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create deposit transaction
            transaction = Transaction.objects.create(
                recipient=user_account,
                amount=amount,
                currency=currency,
                transaction_type='DEPOSIT',
                description="Deposit funds",
                is_successful=True
            )

            # Update balance
            user_account.deposit(amount)

            serializer = self.get_serializer(user_account)
            return Response(serializer.data)

        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid amount"},
                status=status.HTTP_400_BAD_REQUEST
            )


class CurrencyViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for currency operations"""
    queryset = Currency.objects.filter(is_active=True)
    serializer_class = CurrencySerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="List currencies",
        operation_description="List all active currencies",
        responses={
            200: CurrencySerializer(many=True),
            401: "Unauthorized"
        },
        tags=['currencies']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Get currency details",
        operation_description="Get details for a specific currency",
        responses={
            200: CurrencySerializer,
            401: "Unauthorized",
            404: "Currency not found"
        },
        tags=['currencies']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Convert currency",
        operation_description="Convert an amount from one currency to another",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['amount', 'target_currency'],
            properties={
                'amount': openapi.Schema(
                    type=openapi.TYPE_NUMBER,
                    description='Amount to convert',
                    example=100.00
                ),
                'target_currency': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Target currency code (e.g., USD, EUR, RUB)',
                    example='EUR'
                ),
            }
        ),
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'source_currency': openapi.Schema(type=openapi.TYPE_STRING),
                    'target_currency': openapi.Schema(type=openapi.TYPE_STRING),
                    'source_amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                    'converted_amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                    'exchange_rate': openapi.Schema(type=openapi.TYPE_NUMBER),
                }
            ),
            400: "Bad Request - Invalid amount or currency",
            401: "Unauthorized"
        },
        tags=['currencies']
    )
    @action(detail=True, methods=['post'])
    def convert(self, request, pk=None):
        """Convert amount between currencies"""
        try:
            amount = Decimal(request.data.get('amount', 0))
            target_currency_code = request.data.get('target_currency')

            if amount <= 0:
                return Response(
                    {"error": "Amount must be positive"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            source_currency = self.get_object()

            try:
                target_currency = Currency.objects.get(code=target_currency_code)
            except Currency.DoesNotExist:
                return Response(
                    {"error": "Target currency not found"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            converted_amount = source_currency.convert_to(amount, target_currency)

            return Response({
                "source_currency": source_currency.code,
                "target_currency": target_currency.code,
                "source_amount": float(amount),
                "converted_amount": float(converted_amount),
                "exchange_rate": float(target_currency.exchange_rate / source_currency.exchange_rate)
            })

        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid amount"},
                status=status.HTTP_400_BAD_REQUEST
            )


class TransactionViewSet(viewsets.ModelViewSet):
    """ViewSet for transaction operations"""
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['transaction_type', 'is_successful']
    ordering_fields = ['timestamp', 'amount']
    ordering = ['-timestamp']

    @swagger_auto_schema(
        operation_summary="List transactions",
        operation_description="Get a list of transactions with optional filtering",
        manual_parameters=[
            openapi.Parameter(
                'type',
                openapi.IN_QUERY,
                description="Filter by transaction type",
                type=openapi.TYPE_STRING,
                enum=['TRANSFER', 'DEPOSIT', 'WITHDRAWAL', 'CURRENCY_EXCHANGE']
            ),
            openapi.Parameter(
                'start_date',
                openapi.IN_QUERY,
                description="Start date (YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATE
            ),
            openapi.Parameter(
                'end_date',
                openapi.IN_QUERY,
                description="End date (YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATE
            ),
            openapi.Parameter(
                'transaction_type',
                openapi.IN_QUERY,
                description="Transaction type filter",
                type=openapi.TYPE_STRING,
                enum=['TRANSFER', 'DEPOSIT', 'WITHDRAWAL', 'CURRENCY_EXCHANGE']
            ),
            openapi.Parameter(
                'is_successful',
                openapi.IN_QUERY,
                description="Filter by success status",
                type=openapi.TYPE_BOOLEAN
            )
        ],
        responses={
            200: TransactionListSerializer(many=True),
            401: "Unauthorized"
        },
        tags=['transactions']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        """Only return transactions related to the current user"""
        user_account = self.request.user.account

        # Filter by transaction type if provided
        transaction_type = self.request.query_params.get('type')
        if transaction_type:
            queryset = Transaction.objects.filter(
                Q(sender=user_account) | Q(recipient=user_account),
                transaction_type=transaction_type
            )
        else:
            queryset = Transaction.objects.filter(
                Q(sender=user_account) | Q(recipient=user_account)
            )

        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if start_date:
            try:
                start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                queryset = queryset.filter(timestamp__gte=start_datetime)
            except ValueError:
                pass

        if end_date:
            try:
                end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
                # Add one day to include the end date
                end_datetime = end_datetime + timedelta(days=1)
                queryset = queryset.filter(timestamp__lt=end_datetime)
            except ValueError:
                pass

        return queryset

    def get_serializer_class(self):
        """Use different serializers for list and detail views"""
        if self.action == 'list':
            return TransactionListSerializer
        return TransactionSerializer

    @swagger_auto_schema(
        operation_summary="Create transaction",
        operation_description="Create a new transaction",
        request_body=TransactionSerializer,
        responses={
            201: TransactionSerializer,
            400: "Bad Request - Invalid data",
            401: "Unauthorized"
        },
        tags=['transactions']
    )
    def create(self, request, *args, **kwargs):
        """Create a new transaction"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @swagger_auto_schema(
        operation_summary="Recent transactions",
        operation_description="Get transactions from the last 30 days",
        responses={
            200: TransactionListSerializer(many=True),
            401: "Unauthorized"
        },
        tags=['transactions']
    )
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent transactions (last 30 days)"""
        user_account = request.user.account
        thirty_days_ago = timezone.now() - timedelta(days=30)

        transactions = Transaction.objects.filter(
            Q(sender=user_account) | Q(recipient=user_account),
            timestamp__gte=thirty_days_ago
        ).order_by('-timestamp')[:10]

        serializer = TransactionListSerializer(transactions, many=True)
        return Response(serializer.data)


class TransferView(APIView):
    """View for creating transfers"""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Create transfer",
        operation_description="Transfer funds to another account",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['amount', 'currency_id', 'recipient_id'],
            properties={
                'amount': openapi.Schema(
                    type=openapi.TYPE_NUMBER,
                    description='Amount to transfer',
                    example=100.00
                ),
                'currency_id': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Currency code for the transfer',
                    example='USD'
                ),
                'recipient_id': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description='Recipient account ID'
                ),
                'recipient_phone': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Alternative: recipient phone number',
                    example='+1234567890'
                ),
                'description': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Transfer description (optional)',
                    example='Payment for services'
                )
            }
        ),
        responses={
            201: TransactionSerializer,
            400: openapi.Response(
                description="Bad Request",
                examples={
                    "application/json": {
                        "amount": ["Amount must be positive"],
                        "recipient_id": ["Recipient not found"],
                        "currency_id": ["Invalid currency"]
                    }
                }
            ),
            401: "Unauthorized",
            404: "Recipient not found",
            422: "Insufficient funds"
        },
        tags=['transfers']
    )
    def post(self, request, format=None):
        """Create a new transfer"""
        serializer = TransactionSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)