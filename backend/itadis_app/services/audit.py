"""
Сервисный слой для аудита действий
Согласно ТЗ п.5.8 и раздел 8-9
"""
import logging
from typing import Optional, Any
from django.db import transaction

from ..models import User, AuditLog

logger = logging.getLogger(__name__)


def log_action(
    user: Optional[User],
    action: str,
    object_type: str = '',
    object_id: Optional[Any] = None,
    payload: Optional[dict] = None
) -> AuditLog:
    """
    Логирование действия пользователя в журнал аудита
    
    Args:
        user: пользователь, выполнивший действие (None для анонимных)
        action: название действия (например: 'transaction.create', 'login.success')
        object_type: тип объекта, на который повлияло действие
        object_id: ID объекта
        payload: дополнительные данные (будут сохранены как JSON)
    
    Returns:
        AuditLog
    """
    try:
        # Создаём запись в журнале аудита
        # Используем отдельную транзакцию, чтобы логи сохранялись
        # даже если основная операция откатится
        with transaction.atomic():
            audit_log = AuditLog.objects.create(
                user=user,
                action=action,
                object_type=object_type,
                object_id=object_id,
                payload=payload or {}
            )
            
            logger.debug(
                f"Audit log created: {action} by {user.full_name if user else 'Anonymous'}"
            )
            
            return audit_log
            
    except Exception as e:
        # Если не удалось создать лог аудита, логируем ошибку
        # но не прерываем основную операцию
        logger.error(
            f"Failed to create audit log: {e}. "
            f"Action: {action}, User: {user.full_name if user else 'Anonymous'}"
        )
        # Возвращаем None или можно вернуть mock объект
        return None


def log_login_attempt(user: Optional[User], success: bool, ip_address: str = None):
    """
    Логирование попытки входа в систему
    
    Args:
        user: пользователь (None если логин неверный)
        success: успешна ли попытка
        ip_address: IP адрес (опционально)
    """
    action = 'login.success' if success else 'login.failed'
    payload = {}
    
    if ip_address:
        payload['ip_address'] = ip_address
    
    if not success and user is None:
        payload['note'] = 'Invalid credentials'
    
    return log_action(
        user=user,
        action=action,
        payload=payload
    )


def log_permission_denied(user: User, action: str, resource: str):
    """
    Логирование попытки несанкционированного доступа
    
    Args:
        user: пользователь, пытавшийся получить доступ
        action: действие, которое пытался выполнить
        resource: ресурс, к которому пытался получить доступ
    """
    return log_action(
        user=user,
        action='permission.denied',
        payload={
            'attempted_action': action,
            'resource': resource,
            'user_role': user.role
        }
    )
