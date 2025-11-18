from .models import Customer

class CustomerBackend:
    """Authenticate against the Customer model using username/password stored in plain text.
    This is intentionally minimal for the school project. In production, use Django's
    AbstractBaseUser and hashed passwords.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        try:
            user = Customer.objects.get(username=username)
        except Customer.DoesNotExist:
            return None
        # Simple plaintext check (existing project uses plain text passwords)
        if user.password == password:
            return user
        return None

    def get_user(self, user_id):
        try:
            return Customer.objects.get(pk=user_id)
        except Customer.DoesNotExist:
            return None
