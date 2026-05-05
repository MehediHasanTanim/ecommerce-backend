import factory
from factory.django import DjangoModelFactory
from apps.users.models import User, Address

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
    name = factory.Faker('name')
    phone = factory.Sequence(lambda n: f'0171{n:08d}')
    country = factory.Faker('country')
    city = factory.Faker('city')
    area = factory.Faker('street_name')
    postal_code = factory.Faker('postcode')
    address_line = factory.Faker('address')
    type = 'shipping'
    is_default = False
