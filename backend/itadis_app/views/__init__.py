"""
Views для ITadis CRM API
"""
from .auth import *
from .users import *
from .groups import *
from .students import *
from .transactions import *
from .balances import *
from .collections import *
from .expenses import *
from .analytics import (
    analytics_summary, analytics_monthly, analytics_expenses,
    analytics_cashiers, analytics_groups
)
from .audit import *
