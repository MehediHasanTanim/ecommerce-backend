import os
import sys
import argparse
import django

# Add the project root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from apps.users.services import create_user_account
from apps.users.models import User

def main():
    parser = argparse.ArgumentParser(description='Create a user with email, password, and role.')
    parser.add_argument('--email', required=True, help='User email')
    parser.add_argument('--password', required=True, help='User password')
    parser.add_argument('--role', choices=['customer', 'admin', 'staff', 'vendor'], default='customer', help='User role')
    parser.add_argument('--full_name', default='', help='User full name')
    parser.add_argument('--phone', default=None, help='User phone number')

    args = parser.parse_args()

    try:
        if User.objects.filter(email=args.email).exists():
            print(f"Error: User with email {args.email} already exists.")
            sys.exit(1)

        user = create_user_account(
            email=args.email,
            password=args.password,
            role=args.role,
            full_name=args.full_name,
            phone=args.phone,
            is_active=True,
            is_verified=True
        )
        print(f"Success: User created with email: {user.email} and role: {user.role}")
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
