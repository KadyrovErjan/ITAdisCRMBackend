"""
Сервисный слой для бизнес-логики ITadis CRM
"""
from .finance import (
    register_student_payment,
    record_topup_payment,
    collect_money,
    record_expense,
)
from .audit import log_action

__all__ = [
    'register_student_payment',
    'record_topup_payment',
    'collect_money',
    'record_expense',
    'log_action',
]
