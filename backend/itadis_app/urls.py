"""
URL configuration для ITadis CRM API
Согласно ТЗ раздел 6 - базовый префикс /api/v1/
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views.auth import CustomTokenObtainPairView, logout_view
from .views.users import UserViewSet
from .views.groups import GroupViewSet
from .views.students import StudentViewSet
from .views.transactions import TransactionViewSet
from .views.balances import BalanceViewSet
from .views.collections import CollectionViewSet
from .views.expenses import ExpenseViewSet
from .views.audit import AuditLogViewSet
from .views import analytics

# Router для ViewSets
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'groups', GroupViewSet, basename='group')
router.register(r'students', StudentViewSet, basename='student')
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'balances', BalanceViewSet, basename='balance')
router.register(r'collections', CollectionViewSet, basename='collection')
router.register(r'expenses', ExpenseViewSet, basename='expense')
router.register(r'audit-log', AuditLogViewSet, basename='auditlog')

urlpatterns = [
    # Аутентификация
    path('auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/logout/', logout_view, name='logout'),
    
    # Аналитика (только директор)
    path('analytics/summary/', analytics.analytics_summary, name='analytics-summary'),
    path('analytics/monthly/', analytics.analytics_monthly, name='analytics-monthly'),
    path('analytics/expenses/', analytics.analytics_expenses, name='analytics-expenses'),
    path('analytics/cashiers/', analytics.analytics_cashiers, name='analytics-cashiers'),
    path('analytics/groups/', analytics.analytics_groups, name='analytics-groups'),
    
    # ViewSets
    path('', include(router.urls)),
]
