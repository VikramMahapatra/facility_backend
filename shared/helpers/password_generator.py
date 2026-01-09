# Add these at the top with your other imports
import secrets
import string

# Add this password generator function
def generate_secure_password(length=12):
    """Generate a secure random password"""
    if length < 8:
        length = 8
    
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special = "!@#$%^&*"
    
    password_chars = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(special)
    ]
    
    all_chars = uppercase + lowercase + digits + special
    password_chars.extend(secrets.choice(all_chars) for _ in range(length - 4))
    secrets.SystemRandom().shuffle(password_chars)
    
    return ''.join(password_chars)