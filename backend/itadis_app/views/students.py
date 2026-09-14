"""
Views для учеников и транзакций
Согласно ТЗ п.6.3
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.utils.translation import gettext_lazy as _

from ..models import Student
from ..serializers import (
    StudentSerializer, StudentRegistrationSerializer, 
    StudentTopupSerializer, TransactionSerializer
)
from ..permissions import IsCashier
from ..services.finance import register_student_payment, record_topup_payment
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
    queryset = Student.objects.all().select_related('group', 'registered_by').prefetch_related('transactions')
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = StudentFilter
    search_fields = ['full_name']
    ordering_fields = ['created_at', 'full_name']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Кассир видит только своих зарегистрированных учеников"""
        queryset = super().get_queryset()
        
        if self.request.user.role == 'cashier':
            queryset = queryset.filter(registered_by=self.request.user)
        
        return queryset
    
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
            student, transaction = register_student_payment(
                student_data={'full_name': serializer.validated_data['full_name']},
                group_id=serializer.validated_data['group'],
                amount=serializer.validated_data['amount'],
                cashier=request.user
            )
            
            return Response(
                StudentSerializer(student).data,
                status=status.HTTP_201_CREATED
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
    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated, IsCashier])
    def change_status(self, request, pk=None):
        """
        PATCH /api/v1/students/{id}/change_status/
        Изменение статуса ученика (active/debt/frozen/expelled)
        """
        student = self.get_object()
        new_status = request.data.get('status')
        
        if new_status not in ['active', 'debt', 'frozen', 'expelled']:
            return Response(
                {'detail': 'Неверный статус. Допустимые: active, debt, frozen, expelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        student.status = new_status
        student.save()
        
        return Response(StudentSerializer(student).data)
    
    @extend_schema(
        tags=['students'],
        description='Перевод ученика в другую группу',
        request={'type': 'object', 'properties': {'group_id': {'type': 'string', 'format': 'uuid'}}},
        responses={200: StudentSerializer}
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsCashier], url_path='transfer')
    def transfer_group(self, request, pk=None):
        """
        POST /api/v1/students/{id}/transfer/
        Перевод ученика в другую группу
        """
        from ..models import Group
        
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
        student.group = new_group
        student.save()
        
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
            transaction = record_topup_payment(
                student_id=student.id,
                amount=serializer.validated_data['amount'],
                cashier=request.user
            )
            
            return Response(
                TransactionSerializer(transaction).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {'detail': str(e), 'code': 'topup_failed'},
                status=status.HTTP_400_BAD_REQUEST
            )
