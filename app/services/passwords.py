from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

# PasswordHasher defaults are all argon2id parameters:
#   time_cost=3, memory_cost=65536 KiB (64 MiB), parallelism=4
# Argon2id is the PHC winner and the OWASP-recommended default:
# memory-hard, GPU/ASIC-resistant, and it has the combined side-channel
# resistance of the Argon2i variant with the GPU-cracking resistance of
# Argon2d. Hashes include a random 16-byte salt automatically.
_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    """Encode a password as an argon2id string ($argon2id$v=19$m=...)."""
    return _hasher.hash(plain)


def verify_password(plain: str, password_hash: str) -> bool:
    """Constant-time verification; returns False for corrupted hashes too."""
    try:
        return _hasher.verify(password_hash, plain)
    except VerifyMismatchError:
        return False
    except InvalidHashError:
        # Malformed/garbage stored hash: treat as a failed login, don't crash.
        return False
