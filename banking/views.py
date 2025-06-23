from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import api_view, action
from rest_framework_simplejwt.views import TokenObtainPairView
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import UserAccount, Currency, Transaction, CustomUser
from .serializers import (
    UserSerializer,
    UserAccountSerializer,
    CurrencySerializer,
    TransactionSerializer,
    TransactionListSerializer,
    ProfileLoginSerializer
)


class ProfileLoginView(APIView):
    """View for profile login that returns JWT tokens and user details"""
    permission_classes = [AllowAny]
    serializer_class = ProfileLoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = ProfileLoginSerializer(data=request.data)

        if serializer.is_valid():
            validated_data = serializer.validated_data
            user = validated_data['user']

            response_data = {
                'access_token': validated_data['access_token'],
                'refresh_token': validated_data['refresh_token'],
                'user_profile': UserAccountSerializer(validated_data['user_profile']).data
            }

            return Response(response_data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RegisterView(APIView):
    """View for user registration"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    """View for user profile management"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        account = request.user.account
        serializer = UserAccountSerializer(account)
        return Response(serializer.data)

    def patch(self, request):
        account = request.user.account
        serializer = UserAccountSerializer(account, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserAccountViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing user accounts"""
    queryset = UserAccount.objects.all()
    serializer_class = UserAccountSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def my_account(self, request):
        """View own account"""
        user_account = request.user.account
        serializer = self.get_serializer(user_account)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def change_currency(self, request):
        """Change default currency"""
        user_account = request.user.account
        serializer = self.get_serializer(user_account, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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

            currency_code = request.data.get('currency_code', 'USD')
            try:
                currency = Currency.objects.get(code=currency_code)
            except Currency.DoesNotExist:
                return Response(
                    {"error": "Currency not found"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create deposit transaction
            Transaction.objects.create(
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
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['transaction_type', 'is_successful']
    ordering_fields = ['timestamp', 'amount']
    ordering = ['-timestamp']

    def get_queryset(self):
        user_account = self.request.user.account

        queryset = Transaction.objects.filter(
            Q(sender=user_account) | Q(recipient=user_account)
        )

        # Apply filters
        transaction_type = self.request.query_params.get('type')
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)

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
                end_datetime = end_datetime + timedelta(days=1)
                queryset = queryset.filter(timestamp__lt=end_datetime)
            except ValueError:
                pass

        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return TransactionListSerializer
        return TransactionSerializer

    @action(detail=False, methods=['get'])
    def recent(self, request):
        user_account = request.user.account
        thirty_days_ago = timezone.now() - timedelta(days=30)

        transactions = Transaction.objects.filter(
            Q(sender=user_account) | Q(recipient=user_account),
            timestamp__gte=thirty_days_ago
        ).order_by('-timestamp')[:10]

        serializer = TransactionListSerializer(transactions, many=True)
        return Response(serializer.data)


class TransferView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        serializer = TransactionSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def search_accounts(request):
    query = request.GET.get('query', '').strip()

    if not query or len(query) < 2:
        return Response(
            {"error": "Query must be at least 2 characters long"},
            status=status.HTTP_400_BAD_REQUEST
        )

    accounts = UserAccount.objects.filter(
        Q(account_number__icontains=query) |
        Q(user__username__icontains=query) |
        Q(user__email__icontains=query) |
        Q(phone_number__icontains=query)
    ).select_related('user', 'default_currency')[:10]  # Limit results

    results = [{
        'id': account.id,
        'account_number': account.account_number,
        'user': {
            'id': account.user.id,
            'username': account.user.username,
            'email': account.user.email
        },
        'currency': {
            'code': account.default_currency.code,
            'symbol': account.default_currency.symbol
        }
    } for account in accounts]

    return Response(results)