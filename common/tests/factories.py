import factory
from factory.django import DjangoModelFactory
from apps.users.models import User, Address, UserVerificationToken
from django.utils import timezone
from datetime import timedelta

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f'user{n}@example.com')
    phone = factory.Sequence(lambda n: f'0171{n:07d}')
    full_name = factory.Faker('name')
    role = 'customer'
    is_verified = True
    is_active = True

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        password = extracted or "StrongPass123!"
        if create:
            self.set_password(password)
            self.save()

class AdminUserFactory(UserFactory):
    role = 'admin'
    is_staff = True
    is_superuser = True

class StaffUserFactory(UserFactory):
    role = 'staff'
    is_staff = True

class VendorUserFactory(UserFactory):
    role = 'vendor'

class AddressFactory(DjangoModelFactory):
    class Meta:
        model = Address

    user = factory.SubFactory(UserFactory)
    name = factory.Faker('word')
    phone = factory.Sequence(lambda n: f'0171{n:08d}')
    country = factory.Faker('country')
    city = factory.Faker('city')
    area = factory.Faker('street_name')
    postal_code = factory.Faker('postcode')
    address_line = factory.Faker('address')
    type = 'shipping'
    is_default = False

class UserVerificationTokenFactory(DjangoModelFactory):
    class Meta:
        model = UserVerificationToken

    user = factory.SubFactory(UserFactory)
    token_hash = factory.Faker('sha256')
    purpose = 'password_reset'
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(hours=24))
    is_used = False
