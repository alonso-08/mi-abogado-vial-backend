import secrets
import string


def generate_verification_token() -> str:
    """Generar token seguro para verificacion de email"""
    length = 32
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for _ in range(length))
