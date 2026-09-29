"""Key generation for the certificate watermarking framework."""
import os
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

KEYS_DIR = os.path.join(os.path.dirname(__file__), "keys")


def generate_keys():
    os.makedirs(KEYS_DIR, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    priv_pem = private_key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    pub_pem = public_key.public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    with open(os.path.join(KEYS_DIR, "issuer_private.key"), "wb") as f:
        f.write(priv_pem)
    with open(os.path.join(KEYS_DIR, "issuer_public.key"), "wb") as f:
        f.write(pub_pem)
    print("Keys written to", KEYS_DIR)


def load_private_key():
    with open(os.path.join(KEYS_DIR, "issuer_private.key"), "rb") as f:
        return Ed25519PrivateKey.from_private_bytes(f.read())


def load_public_key_bytes():
    with open(os.path.join(KEYS_DIR, "issuer_public.key"), "rb") as f:
        return f.read()


def load_public_key():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    return Ed25519PublicKey.from_public_bytes(load_public_key_bytes())


if __name__ == "__main__":
    generate_keys()
