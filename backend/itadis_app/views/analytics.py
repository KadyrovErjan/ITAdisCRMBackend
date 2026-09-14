"""
Views для аналитики
Согласно ТЗ п.6.7 - только для директора
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from django.http import HttpResponse
from datetime import datetime
import io

from ..serializers import (
    AnalyticsSummarySerializer, AnalyticsMonthlySerializer,
    AnalyticsExpensesByUserSerializer
)
from ..permissions import CanViewAnalytics
from ..services.analytics import (
    get_summary_analytics, get_monthly_analytics,
    get_expenses_by_user, get_cashier_statistics,
    get_group_statistics
)


@extend_schema(
    tags=['analytics'],
    description='Общая сводка: доход, расход, прибыль за период',
    responses={200: AnalyticsSummarySerializer}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, CanViewAnalytics])
def analytics_summary(request):
    """
    GET /api/v1/analytics/summary/
    { total_income, total_expense, net_profit }
    Параметры: ?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
    """
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    
    # Парсим даты если указаны
    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'detail': 'Неверный формат date_from. Используйте YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'detail': 'Неверный формат date_to. Используйте YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    data = get_summary_analytics(date_from=date_from, date_to=date_to)
    serializer = AnalyticsSummarySerializer(data)
    return Response(serializer.data)


@extend_schema(
    tags=['analytics'],
    description='Помесячная разбивка доходов/расходов',
    responses={200: AnalyticsMonthlySerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, CanViewAnalytics])
def analytics_monthly(request):
    """
    GET /api/v1/analytics/monthly/
    [{ month, income, expense, profit }, ...]
    Параметры: ?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
    """
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    
    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    data = get_monthly_analytics(date_from=date_from, date_to=date_to)
    serializer = AnalyticsMonthlySerializer(data, many=True)
    return Response(serializer.data)


@extend_schema(
    tags=['analytics'],
    description='Детальный отчёт по расходам с группировкой по пользователям',
    responses={200: AnalyticsExpensesByUserSerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, CanViewAnalytics])
def analytics_expenses(request):
    """
    GET /api/v1/analytics/expenses/
    Расходы с фильтрами
    Параметры: ?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&user_id=UUID
    """
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    user_id = request.query_params.get('user_id')
    
    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    data = get_expenses_by_user(date_from=date_from, date_to=date_to, user_id=user_id)
    serializer = AnalyticsExpensesByUserSerializer(data, many=True)
    return Response(serializer.data)


@extend_schema(
    tags=['analytics'],
    description='Статистика по кассирам',
    responses={200: dict}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, CanViewAnalytics])
def analytics_cashiers(request):
    """
    GET /api/v1/analytics/cashiers/
    Статистика по кассирам (сколько приняли денег)
    """
    cashier_id = request.query_params.get('cashier_id')
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    
    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    data = get_cashier_statistics(cashier_id=cashier_id, date_from=date_from, date_to=date_to)
    return Response(data)


@extend_schema(
    tags=['analytics'],
    description='Статистика по группам',
    responses={200: dict}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, CanViewAnalytics])
def analytics_groups(request):
    """
    GET /api/v1/analytics/groups/
    Статистика по группам (количество учеников, собранные суммы)
    """
    data = get_group_statistics()
    return Response(data)

