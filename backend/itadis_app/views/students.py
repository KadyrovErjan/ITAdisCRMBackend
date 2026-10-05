"""
Views для учеников и транзакций
Согласно ТЗ п.6.3
"""
from decimal import Decimal

from django.db.models import DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view

from ..models import Group, Student
from ..serializers import (
    StudentSerializer, StudentRegistrationSerializer, 
    StudentDetailsUpdateSerializer, StudentStatusSerializer,
    StudentTopupSerializer, TransactionSerializer
)
from ..permissions import IsCashier, IsCashierOrDirector
from ..services.audit import log_action
from ..services.finance import register_student_payment, record_student_payment
from ..filters import StudentFilter


@extend_schema_view(
    list=extend_schema(tags=['students'], description='Список учеников'),
    retrieve=extend_schema(tags=['students'], description='Детали ученика'),
)
class StudentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для учеников
    Создание через отдельный action (register)
    """
    queryset = Student.objects.all().select_related('group', 'registered_by')
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = StudentFilter
    search_fields = ['full_name', 'phone']
    ordering_fields = ['created_at', 'full_name', 'remaining_balance_annotated']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Кассир видит только своих зарегистрированных учеников"""
        money_field = DecimalField(max_digits=12, decimal_places=2)
        queryset = super().get_queryset().annotate(
            total_paid=Coalesce(
                Sum('transactions__amount'),
                Value(Decimal('0.00')),
                output_field=money_field,
            ),
            booking_paid=Coalesce(
                Sum('transactions__amount', filter=Q(transactions__type='booking')),
                Value(Decimal('0.00')),
                output_field=money_field,
            ),
        ).annotate(remaining_balance_annotated=F('course_price') - F('total_paid'))
        
        if self.request.user.role == 'cashier':
            queryset = queryset.filter(registered_by=self.request.user)
        
        return queryset

    def get_permissions(self):
        if self.action in {'register', 'payments', 'booking'}:
            return [IsAuthenticated(), IsCashier()]
        if self.action in {'change_status', 'transfer_group', 'update_details'}:
            return [IsAuthenticated(), IsCashierOrDirector()]
        return super().get_permissions()

    @staticmethod
    def _idempotency_key(request):
        return request.headers.get('Idempotency-Key') or request.data.get('idempotency_key')
    
    @extend_schema(
        tags=['students'],
        description='Регистрация нового ученика с первым платежом',
        request=StudentRegistrationSerializer,
        responses={201: StudentSerializer}
    )
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsCashier])
    def register(self, request):
        """
        POST /api/v1/students/register/
        Регистрация ученика + первый платёж
        Атомарно создаёт Student, Transaction(register) и увеличивает Balance кассира
        """
        serializer = StudentRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            student_data = {
                key: serializer.validated_data.get(key)
                for key in ('full_name', 'phone', 'assistant_name', 'comment', 'contract_status', 'course_price')
                if serializer.validated_data.get(key) is not None
            }
            student, transactions, replayed = register_student_payment(
                student_data=student_data,
                group_id=serializer.validated_data['group'],
                amount=serializer.validated_data['amount'],
                booking_amount=serializer.validated_data['booking_amount'],
                cashier=request.user,
                idempotency_key=self._idempotency_key(request),
            )
            
            return Response(
                {
                    'student': StudentSerializer(student).data,
                    'transaction_ids': [str(item.id) for item in transactions],
                    'replayed': replayed,
                },
                status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {'detail': str(e), 'code': 'registration_failed'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @extend_schema(
        tags=['students'],
        description='Изменение статуса ученика',
        request={'type': 'object', 'properties': {'status': {'type': 'string', 'enum': ['active', 'debt', 'frozen', 'expelled']}}},
        responses={200: StudentSerializer}
    )
    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated, IsCashierOrDirector])
    def change_status(self, request, pk=None):
        """
        PATCH /api/v1/students/{id}/change_status/
        Изменение статуса ученика (active/debt/frozen/expelled)
        """
        student = self.get_object()
        serializer = StudentStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        old_status = student.status
        new_status = serializer.validated_data['status']
        student.status = new_status
        student.save(update_fields=['status'])
        log_action(
            user=request.user,
            action='student.status.change',
            object_type='Student',
            object_id=student.id,
            payload={'old_status': old_status, 'new_status': new_status},
        )
        
        return Response(StudentSerializer(student).data)
    
    @extend_schema(
        tags=['students'],
        description='Перевод ученика в другую группу',
        request={'type': 'object', 'properties': {'group_id': {'type': 'string', 'format': 'uuid'}}},
        responses={200: StudentSerializer}
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsCashierOrDirector], url_path='transfer')
    def transfer_group(self, request, pk=None):
        """
        POST /api/v1/students/{id}/transfer/
        Перевод ученика в другую группу
        """
        student = self.get_object()
        new_group_id = request.data.get('group_id')
        
        if not new_group_id:
            return Response(
                {'detail': 'Требуется указать group_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            new_group = Group.objects.get(id=new_group_id)
        except Group.DoesNotExist:
            return Response(
                {'detail': 'Группа не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        old_group = student.group
        if new_group.id == old_group.id:
            return Response(
                {'detail': 'Ученик уже находится в этой группе'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if request.user.role == 'cashier' and new_group.created_by_id != request.user.id:
            return Response({'detail': 'Недоступная для вас группа'}, status=status.HTTP_403_FORBIDDEN)
        student.group = new_group
        student.save(update_fields=['group'])
        log_action(
            user=request.user,
            action='student.transfer',
            object_type='Student',
            object_id=student.id,
            payload={'from_group_id': str(old_group.id), 'to_group_id': str(new_group.id)},
        )
        
        return Response({
            'detail': f'Ученик переведен из группы "{old_group.name}" в группу "{new_group.name}"',
            'student': StudentSerializer(student).data
        })
    
    @extend_schema(
        tags=['students'],
        description='Прием доплаты от ученика',
        request=StudentTopupSerializer,
        responses={201: TransactionSerializer}
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsCashier])
    def payments(self, request, pk=None):
        """
        POST /api/v1/students/{id}/payments/
        Приём доплаты (topup)
        Атомарно создаёт Transaction и увеличивает Balance
        """
        student = self.get_object()
        serializer = StudentTopupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            transaction, replayed = record_student_payment(
                student_id=student.id,
                amount=serializer.validated_data['amount'],
                cashier=request.user,
                payment_type='topup',
                idempotency_key=self._idempotency_key(request),
            )
            
            return Response(
                {'transaction': TransactionSerializer(transaction).data, 'replayed': replayed},
                status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {'detail': str(e), 'code': 'payment_failed'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsCashier])
    def booking(self, request, pk=None):
        """Принять бронь как отдельную append-only транзакцию."""
        student = self.get_object()
        serializer = StudentTopupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            transaction, replayed = record_student_payment(
                student_id=student.id,
                amount=serializer.validated_data['amount'],
                cashier=request.user,
                payment_type='booking',
                idempotency_key=self._idempotency_key(request),
            )
            return Response(
                {'transaction': TransactionSerializer(transaction).data, 'replayed': replayed},
                status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
            )
        except Exception as error:
            return Response({'detail': str(error), 'code': 'booking_failed'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated, IsCashierOrDirector])
    def update_details(self, request, pk=None):
        """Изменить только разрешённые не финансовые данные ученика."""
        student = self.get_object()
        serializer = StudentDetailsUpdateSerializer(student, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        changed_fields = [
            field for field, value in serializer.validated_data.items()
            if getattr(student, field) != value
        ]
        serializer.save()
        if changed_fields:
            log_action(
                user=request.user,
                action='student.details.update',
                object_type='Student',
                object_id=student.id,
                payload={'fields': changed_fields},
            )
        return Response(StudentSerializer(student).data)

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """История всех поступлений ученика."""
        student = self.get_object()
        transactions = student.transactions.select_related('cashier', 'student__group').all()
        page = self.paginate_queryset(transactions)
        if page is not None:
            return self.get_paginated_response(TransactionSerializer(page, many=True).data)
        return Response(TransactionSerializer(transactions, many=True).data)
