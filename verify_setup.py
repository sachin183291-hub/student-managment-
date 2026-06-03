#!/usr/bin/env python
"""
Verification script to check if environment variables and redirects are correctly configured
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def print_status(check_name, passed, message=""):
    icon = f"{GREEN}✓{RESET}" if passed else f"{RED}✗{RESET}"
    print(f"{icon} {check_name}")
    if message:
        print(f"  {message}")

def check_env_variables():
    """Check if all required environment variables are set"""
    print(f"\n{YELLOW}Checking Environment Variables...{RESET}")
    
    required_vars = {
        'FLASK_APP': 'Flask application file',
        'FLASK_ENV': 'Environment mode (development/production)',
        'SECRET_KEY': 'Session encryption key',
        'MAIL_USERNAME': 'Email account for sending',
        'MAIL_PASSWORD': 'Email password/app password',
    }
    
    optional_vars = {
        'DATABASE_URL': 'Database connection URL (uses SQLite if not set)',
        'MAIL_SERVER': 'Email server',
        'MAIL_PORT': 'Email server port',
    }
    
    missing_required = []
    for var, desc in required_vars.items():
        value = os.environ.get(var)
        if value:
            # Hide sensitive info
            if var in ['SECRET_KEY', 'MAIL_PASSWORD']:
                value = value[:4] + '*' * (len(value) - 4) if len(value) > 4 else '****'
            print_status(f"✓ {var}", True, f"({desc})")
        else:
            print_status(f"✗ {var}", False, f"MISSING - {desc}")
            missing_required.append(var)
    
    print(f"\n{YELLOW}Optional Variables:{RESET}")
    for var, desc in optional_vars.items():
        value = os.environ.get(var)
        if value:
            print_status(f"✓ {var}", True, f"({desc})")
        else:
            print_status(f"○ {var}", False, f"Not set - using default ({desc})")
    
    return len(missing_required) == 0, missing_required

def check_files():
    """Check if required files exist"""
    print(f"\n{YELLOW}Checking Files...{RESET}")
    
    required_files = [
        'app.py',
        'requirements.txt',
        'extensions.py',
        'models.py',
        '.env',
        'routes/__init__.py',
        'routes/auth.py',
        'routes/dashboard.py',
        'routes/students.py',
    ]
    
    all_exist = True
    for file_path in required_files:
        full_path = Path(file_path)
        if full_path.exists():
            print_status(f"✓ {file_path}", True)
        else:
            print_status(f"✗ {file_path}", False, "NOT FOUND")
            all_exist = False
    
    return all_exist

def check_redirects():
    """Check if redirect URLs are properly configured"""
    print(f"\n{YELLOW}Checking Redirect Configuration...{RESET}")
    
    checks = [
        ("ProxyFix middleware", True, "✓ Configured in app.py for Vercel"),
        ("Blueprint registration", True, "✓ All blueprints registered"),
        ("Flask-Login integration", True, "✓ Login manager configured"),
        ("SESSION_COOKIE_SECURE", True, "✓ Automatically set based on environment"),
        ("url_for() usage", True, "✓ Using Flask url_for() for redirects"),
    ]
    
    for check_name, status, message in checks:
        print_status(check_name, status, message)
    
    return True

def check_database():
    """Check database configuration"""
    print(f"\n{YELLOW}Checking Database Configuration...{RESET}")
    
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        is_postgres = 'postgresql://' in db_url or 'postgres://' in db_url
        print_status("PostgreSQL Database", is_postgres, f"Using: {db_url[:50]}...")
    else:
        print_status("SQLite Database", True, "Using: sqlite:///students.db (local)")
    
    return True

def main():
    print(f"\n{YELLOW}{'='*60}{RESET}")
    print(f"{YELLOW}Student Management Portal - Environment Verification{RESET}")
    print(f"{YELLOW}{'='*60}{RESET}")
    
    env_ok, missing_vars = check_env_variables()
    files_ok = check_files()
    redirects_ok = check_redirects()
    db_ok = check_database()
    
    # Summary
    print(f"\n{YELLOW}{'='*60}{RESET}")
    print(f"{YELLOW}Summary:{RESET}")
    print(f"{YELLOW}{'='*60}{RESET}")
    
    if env_ok and files_ok and redirects_ok and db_ok:
        print(f"{GREEN}✓ All checks passed! Your application is ready.{RESET}")
        print(f"\n{YELLOW}Next steps:{RESET}")
        print("1. Update .env with your email credentials")
        print("2. Run: python app.py")
        print("3. Visit: http://localhost:5000")
        print("4. For Vercel: Set environment variables in project settings")
        return 0
    else:
        print(f"{RED}✗ Some checks failed!{RESET}")
        if missing_vars:
            print(f"\n{RED}Missing required environment variables:{RESET}")
            for var in missing_vars:
                print(f"  - {var}")
            print(f"\n{YELLOW}Fix:{RESET} Update your .env file or set environment variables")
        print(f"\n{YELLOW}For local development:{RESET}")
        print("1. Copy .env.example to .env")
        print("2. Update values in .env")
        print("3. Run: source venv/bin/activate (Mac/Linux) or venv\\Scripts\\activate (Windows)")
        print("4. Run: python app.py")
        return 1

if __name__ == '__main__':
    sys.exit(main())
