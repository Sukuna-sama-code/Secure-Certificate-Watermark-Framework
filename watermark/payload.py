"""Payload construction: hash certificate content, sign it, add error correction.

Payload layout (total 720 bits = 90 bytes):
  [ 0: 16)  SHA-256 digest of certificate content, truncated to 16 bytes
  [16: 80)  Ed25519 signature over that 16-byte digest (full, untruncated)
  [80: 90)  even-parity bits: one parity bit per body byte, packed

The verifier recomputes the digest from the *presented* certificate, so any
edit to the certificate changes the digest -> signature check fails -> TAMPERED.
"""
import hashlib

import numpy as np

PAYLOAD_BITS = 720
MAGIC = b"CWAT"  # domain-separation prefix for hashing


def _to_bits(data: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))


def _from_bits(bits: np.ndarray) -> bytes:
    return np.packbits(bits.astype(np.uint8)).tobytes()


def content_digest(certificate_bytes: bytes) -> bytes:
    return hashlib.sha256(MAGIC + certificate_bytes).digest()[:16]


def _parity_block(data: bytes) -> bytes:
    """One even-parity bit per input byte, packed (ceil(len/8) bytes)."""
    out = bytearray((len(data) + 7) // 8)
    for i, b in enumerate(data):
        if format(b, "08b").count("1") % 2:
            out[i // 8] |= 1 << (7 - (i % 8))
    return bytes(out)


def _parity_score(body: bytes, parity: bytes) -> float:
    expected = _to_bits(_parity_block(body))
    given = _to_bits(parity[: len(expected)])
    return float(np.mean(expected == given))


def parity_score_from_bits(bits: np.ndarray) -> float:
    """Self-check score for an extracted payload (0.5 ~ garbage, 1.0 ~ clean)."""
    payload = _from_bits(bits[:PAYLOAD_BITS])
    return _parity_score(payload[:80], payload[80:90])


def build_payload(certificate_bytes: bytes, private_key) -> np.ndarray:
    digest = content_digest(certificate_bytes)          # 16 bytes
    signature = private_key.sign(digest)                # 64 bytes (Ed25519)
    body = digest + signature                           # 80 bytes
    payload = body + _parity_block(body)                # 90 bytes = 720 bits
    assert len(payload) * 8 == PAYLOAD_BITS
    return _to_bits(payload)


def verify_payload(bits: np.ndarray, public_key, certificate_bytes: bytes) -> dict:
    payload = _from_bits(bits[:PAYLOAD_BITS])
    body, parity = payload[:80], payload[80:90]
    digest, signature = body[:16], body[16:80]

    recomputed = content_digest(certificate_bytes)
    hash_ok = digest == recomputed
    parity_score = _parity_score(body, parity)

    sig_ok = False
    try:
        public_key.verify(signature, digest)
        sig_ok = True
    except Exception:
        sig_ok = False

    if sig_ok and hash_ok:
        verdict = "AUTHENTIC"
    elif sig_ok and not hash_ok:
        verdict = "TAMPERED"
    elif parity_score >= 0.9:
        # watermark structure present but signature invalid -> re-signed/forged mark
        verdict = "FORGED"
    else:
        verdict = "FORGED"
    return {
        "verdict": verdict,
        "hash_ok": hash_ok,
        "signature_ok": sig_ok,
        "parity_score": round(parity_score, 3),
    }
