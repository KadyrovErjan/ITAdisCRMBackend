"""
Кастомный обработчик исключений для единообразного формата ошибок API
Согласно ТЗ раздел 6.8 - формат: { "detail": "сообщение", "code": "machine_readable_code" }
"""
from rest_framework.views import exception_handler
from rest_framework.exceptions import ErrorDetail
from django.utils.translation import gettext_lazy as _
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Кастомный обработчик для единого формата ошибок API
    """
    # Вызываем стандартный обработчик DRF
    response = exception_handler(exc, context)
    
    if response is not None:
        # Получаем пользователя безопасно (без доступа к БД если транзакция грязная)
        request = context.get('request')
        user = None
        try:
            if request and hasattr(request, 'user'):
                # Пытаемся получить пользователя только если он уже загружен
                user = request.user if hasattr(request.user, 'id') else None
        except Exception:
            # Игнорируем ошибки при получении пользователя
            pass
        
        # Логируем ошибку
        logger.error(
            f"API Error: {exc.__class__.__name__} - {str(exc)} | Path: {getattr(request, 'path', 'N/A') if request else 'N/A'} | Method: {getattr(request, 'method', 'N/A') if request else 'N/A'}",
            extra={
                'status_code': response.status_code,
                'user': user,
                'path': getattr(request, 'path', None) if request else None,
                'exc_detail': repr(exc),
            }
        )
        
        # Преобразуем к единому формату
        custom_response_data = {}
        
        if isinstance(response.data, dict):
            # Если есть поле detail, используем его
            if 'detail' in response.data:
                custom_response_data['detail'] = str(response.data['detail'])
            else:
                # Иначе объединяем все ошибки
                errors = []
                for key, value in response.data.items():
                    if isinstance(value, list):
                        errors.extend([str(v) for v in value])
                    else:
                        errors.append(str(value))
                custom_response_data['detail'] = '; '.join(errors)
        elif isinstance(response.data, list):
            custom_response_data['detail'] = '; '.join([str(item) for item in response.data])
        else:
            custom_response_data['detail'] = str(response.data)
        
        # Добавляем машиночитаемый код ошибки
        error_code = getattr(exc, 'default_code', 'error')
        custom_response_data['code'] = error_code
        
        response.data = custom_response_data
    
    return response
