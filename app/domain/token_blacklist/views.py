from sqladmin import Admin, ModelView
from .models import TokenBlacklist

class TokenBlacklistView(ModelView, model=TokenBlacklist):
    column_list = [
        'token', 'expiration_date'
    ]
