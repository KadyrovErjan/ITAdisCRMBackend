"""Read-only dashboard data for the cashier workspace."""
from decimal import Decimal

from django.db.models import DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import Balance, Student, Transaction
from ..permissions import IsCashier
from ..serializers import StudentSerializer, TransactionSerializer


def _with_financial_totals(queryset):
    money_field = DecimalField(max_digits=12, decimal_places=2)
    return queryset.annotate(
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


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCashier])
def cashier_dashboard(request):
    """Cashier-only operational metrics and compact recent activity lists."""
    today = timezone.localdate()
    month_start = today.replace(day=1)
    own_students = _with_financial_totals(
        Student.objects.filter(registered_by=request.user).select_related('group', 'registered_by')
    )
    own_transactions = Transaction.objects.filter(cashier=request.user).select_related(
        'student', 'student__group', 'cashier'
    )

    today_transactions = own_transactions.filter(created_at__date=today)
    month_transactions = own_transactions.filter(created_at__date__gte=month_start)
    debt_students = own_students.filter(course_price__isnull=False, remaining_balance_annotated__gt=0)
    balance = Balance.objects.filter(user=request.user).values_list('amount', flat=True).first() or Decimal('0.00')

    return Response({
        'balance': str(balance),
        'today_received': str(today_transactions.aggregate(
            total=Coalesce(
                Sum('amount'), Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )['total']),
        'today_payments_count': today_transactions.count(),
        'month_received': str(month_transactions.aggregate(
            total=Coalesce(
                Sum('amount'), Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )['total']),
        'debt_students_count': debt_students.count(),
        'recent_transactions': TransactionSerializer(own_transactions[:10], many=True).data,
        'recent_students': StudentSerializer(own_students.order_by('-created_at')[:10], many=True).data,
    })
