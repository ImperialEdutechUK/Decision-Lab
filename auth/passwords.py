"""Password hashing for admin accounts (bcrypt, used directly to avoid the passlib/bcrypt-4
version shim warning). bcrypt limits inputs to 72 bytes, which is ample for passwords."""
import bcrypt


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False
