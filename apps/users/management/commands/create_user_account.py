from django.core.management.base import BaseCommand, CommandError
from apps.users.services import create_user_account
from apps.users.models import User

class Command(BaseCommand):
    help = 'Create a new user account'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, required=True, help='User email')
        parser.add_argument('--password', type=str, required=True, help='User password')
        parser.add_argument('--role', type=str, choices=['customer', 'admin', 'staff', 'vendor'], default='customer', help='User role')
        parser.add_argument('--full_name', type=str, default='', help='User full name')
        parser.add_argument('--phone', type=str, default=None, help='User phone number')

    def handle(self, *args, **options):
        email = options['email']
        password = options['password']
        role = options['role']
        full_name = options['full_name']
        phone = options['phone']

        if User.objects.filter(email=email).exists():
            self.stderr.write(self.style.ERROR(f'User with email "{email}" already exists.'))
            return

        try:
            user = create_user_account(
                email=email,
                password=password,
                role=role,
                full_name=full_name,
                phone=phone,
                is_active=True,
                is_verified=True
            )
            self.stdout.write(self.style.SUCCESS(f'Successfully created user "{user.email}" with role "{user.role}"'))
        except Exception as e:
            raise CommandError(f'Error creating user: {str(e)}')
