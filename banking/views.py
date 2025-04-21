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


class UserProfileView(RetrieveUpdateAPIView):
    """View for user profile management"""
    permission_classes = [IsAuthenticated]
    serializer_class = UserAccountSerializer
    
    def get_object(self):
        """Return the logged-in user's account"""
        return self.request.user.account


class UserAccountViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing user accounts"""
    queryset = UserAccount.objects.all()
    serializer_class = UserAccountSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def my_accounts(self, request):
        """View own accounts"""
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
    
    def create(self, request, *args, **kwargs):
        """Create a new transaction"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
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
