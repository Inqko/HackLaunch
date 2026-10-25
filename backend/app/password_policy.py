import re

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128

_COMMON_PASSWORDS = {
    "password",
    "password1",
    "password123",
    "12345678",
    "123456789",
    "1234567890",
    "qwerty123",
    "qwertyui",
    "qwertyuiop",
    "iloveyou",
    "admin123",
    "welcome1",
    "letmein1",
    "abc12345",
    "passw0rd",
    "hacklaunch",
}


def password_policy_error(password: str) -> str | None:
    """Возвращает текст первой ошибки политики паролей или None, если пароль надёжен."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Пароль должен содержать минимум {PASSWORD_MIN_LENGTH} символов"
    if len(password) > PASSWORD_MAX_LENGTH:
        return f"Пароль должен содержать не более {PASSWORD_MAX_LENGTH} символов"
    if password.lower() in _COMMON_PASSWORDS:
        return "Этот пароль слишком распространён — выберите другой"
    if not re.search(r"[a-z]", password):
        return "Добавьте хотя бы одну строчную букву"
    if not re.search(r"[A-Z]", password):
        return "Добавьте хотя бы одну заглавную букву"
    if not re.search(r"\d", password):
        return "Добавьте хотя бы одну цифру"
    if not re.search(r"[^A-Za-z0-9]", password):
        return "Добавьте хотя бы один специальный символ (например, !@#$%)"
    if len(set(password)) < 4:
        return "Пароль слишком простой — используйте больше разных символов"
    return None
