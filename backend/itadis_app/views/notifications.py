from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from ..models import PaymentNotification
from ..services.payment_plans import item_outstanding


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_notifications(request):
    queryset = PaymentNotification.objects.filter(recipient=request.user, resolved_at__isnull=True).select_related('student__group', 'schedule_item')
    if request.query_params.get('unread') == 'true':
        queryset = queryset.filter(read_at__isnull=True)
    data = [{
        'id': str(item.id), 'kind': item.kind, 'message': item.message,
        'student_id': str(item.student_id), 'student_name': item.student.full_name,
        'group_id': str(item.student.group_id), 'group_name': item.student.group.name,
        'due_date': item.schedule_item.due_date, 'amount': str(item_outstanding(item.schedule_item)),
        'read_at': item.read_at, 'created_at': item.created_at,
    } for item in queryset.order_by('-created_at')]
    return Response({'count': len(data), 'unread_count': sum(1 for item in data if item['read_at'] is None), 'results': data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_payment_notification_read(request, pk):
    notification = PaymentNotification.objects.filter(pk=pk, recipient=request.user).first()
    if not notification:
        return Response({'detail': 'Уведомление не найдено'}, status=status.HTTP_404_NOT_FOUND)
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=['read_at'])
    return Response({'id': str(notification.id), 'read_at': notification.read_at})
