"""
Debug middleware для логирования всех запросов
"""
import logging

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """
    Middleware для логирования всех входящих запросов
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Логируем входящий запрос
        auth_header = request.META.get('HTTP_AUTHORIZATION', 'NO AUTH')
        logger.info(f">>> REQUEST: {request.method} {request.path} | Query: {request.GET.dict()} | Content-Type: {request.content_type}")
        logger.info(f">>> Authorization: {auth_header[:50] if len(auth_header) > 50 else auth_header}...")
        
        # Пробуем резолвить URL
        from django.urls import resolve, Resolver404
        try:
            match = resolve(request.path)
            logger.info(f">>> URL RESOLVED: {match.func.__name__ if hasattr(match.func, '__name__') else match.func} | name: {match.url_name}")
        except Resolver404 as e:
            logger.error(f">>> URL NOT RESOLVED: {e}")
        
        # Обрабатываем запрос
        response = self.get_response(request)
        
        # Логируем ответ
        logger.info(f"<<< RESPONSE: {response.status_code} | Content-Type: {response.get('Content-Type', 'N/A')}")
        if response.status_code == 404:
            logger.error(f"<<< 404 RESPONSE CONTENT: {response.content[:500] if hasattr(response, 'content') else 'N/A'}")
        
        return response
