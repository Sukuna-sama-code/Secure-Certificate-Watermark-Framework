"""DCT-based spread-spectrum watermark embedder.

Method (Cox et al. style, block-based):
  1. Convert certificate image to YCbCr, take the luminance (Y) channel.
  2. Split into 8x8 blocks, apply DCT to each.
  3. Embed one payload bit into each block's mid-frequency coefficient
     using quantization-index modulation (QIM):
        coeff is snapped to the nearest even/odd multiple of Q
        (even -> bit 0, odd -> bit 1).
  4. Inverse DCT, merge back, convert to BGR, save.

QIM is chosen over additive spread-spectrum because extraction is blind
(no original image needed) and robust to mild noise/compression.
Q (quantization step) trades off: larger Q = more robust, more visible.
"""
import cv2
import numpy as np

from .payload import PAYLOAD_BITS, parity_score_from_bits

BLOCK = 8
Q = 24.0  # quantization step

# Mid-frequency coefficient position in the 8x8 DCT block (row, col)
COEF = (4, 3)

_D, _I = np.meshgrid(np.arange(BLOCK), np.arange(BLOCK))
_DCT_M = np.sqrt(2.0 / BLOCK) * np.cos((2 * _D + 1) * _I * np.pi / (2 * BLOCK))
_DCT_M[0, :] = np.sqrt(1.0 / BLOCK)


def _dct_blocks(blocks: np.ndarray) -> np.ndarray:
    return _DCT_M @ blocks @ _DCT_M.T


def _idct_blocks(blocks: np.ndarray) -> np.ndarray:
    return _DCT_M.T @ blocks @ _DCT_M


def _bit_at(bits: np.ndarray, i: int) -> int:
    return int(bits[i % len(bits)])


def embed_image(img: np.ndarray, payload_bits: np.ndarray) -> np.ndarray:
    ycbcr = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb).astype(np.float32)
    y = ycbcr[:, :, 0]

    h, w = y.shape
    hb, wb = h // BLOCK, w // BLOCK
    if hb * wb < PAYLOAD_BITS:
        raise ValueError(f"Image too small: {hb*wb} blocks < {PAYLOAD_BITS} bits needed")

    y_blocks = y[: hb * BLOCK, : wb * BLOCK].reshape(hb, BLOCK, wb, BLOCK)
    y_blocks = np.ascontiguousarray(y_blocks.transpose(0, 2, 1, 3), dtype=np.float32)
    flat = np.ascontiguousarray(y_blocks.reshape(-1, BLOCK, BLOCK), dtype=np.float32)

    r, c = COEF
    dct_all = _dct_blocks(flat)
    coeffs = dct_all[:, r, c].copy()

    bits = np.array([_bit_at(payload_bits, i) for i in range(coeffs.size)])
    # QIM: bit 0 -> nearest lattice point at an EVEN multiple of Q,
    #       bit 1 -> nearest point at an ODD multiple of Q.
    base = 2 * np.floor(coeffs / (2 * Q))  # even integer index
    idx = np.arange(coeffs.size)
    cand0 = np.stack([base - 2, base, base + 2]) * Q
    cand1 = np.stack([base - 1, base + 1, base + 3]) * Q
    chosen0 = cand0[np.argmin(np.abs(cand0 - coeffs), axis=0), idx]
    chosen1 = cand1[np.argmin(np.abs(cand1 - coeffs), axis=0), idx]
    new_coeffs = np.where(bits == 0, chosen0, chosen1)

    dct_all[:, r, c] = new_coeffs
    rebuilt = _idct_blocks(dct_all).reshape(hb, wb, BLOCK, BLOCK)
    y_new = np.ascontiguousarray(rebuilt.transpose(0, 2, 1, 3)).reshape(hb * BLOCK, wb * BLOCK)

    ycbcr[: hb * BLOCK, : wb * BLOCK, 0] = y_new
    return cv2.cvtColor(np.clip(ycbcr, 0, 255).astype(np.uint8), cv2.COLOR_YCrCb2BGR)


def _coeffs(img: np.ndarray) -> np.ndarray:
    ycbcr = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb).astype(np.float32)
    y = ycbcr[:, :, 0]
    h, w = y.shape
    hb, wb = h // BLOCK, w // BLOCK
    y_blocks = y[: hb * BLOCK, : wb * BLOCK].reshape(hb, BLOCK, wb, BLOCK)
    y_blocks = np.ascontiguousarray(y_blocks.transpose(0, 2, 1, 3), dtype=np.float32)
    flat = np.ascontiguousarray(y_blocks.reshape(-1, BLOCK, BLOCK), dtype=np.float32)
    r, c = COEF
    return _dct_blocks(flat)[:, r, c]


def _lattice_confidence(coeffs: np.ndarray) -> float:
    """How closely the coefficients sit on the QIM grid (1.0 = perfect).

    A genuine watermark snaps coefficients onto multiples of Q at embed
    time, so residual distance is ~0. Destroyed or absent watermarks
    leave arbitrary coefficients ~uniform in [-Q/2, Q/2], conf <= ~0.5.
    """
    n = max(coeffs.size, 1)
    dist = np.abs(coeffs[:n] / Q - np.round(coeffs[:n] / Q))
    return float(np.clip(1.0 - 2.0 * dist.mean(), 0.0, 1.0))


def _vote_bits(coeffs: np.ndarray):
    """Majority-vote decode across the repeated payload copies.

    The embedder repeats the 720-bit payload across all available blocks
    (~30x for a 1024x1400 certificate). Per-block errors from attacks are
    largely independent, so voting recovers bits that individual blocks
    lost. Returns (bits, margin) where margin is the mean distance of the
    vote from a tie (0.5 = no signal, 1.0 = unanimous).
    """
    n = (coeffs.size // PAYLOAD_BITS) * PAYLOAD_BITS
    votes = (np.round(coeffs[:n] / Q).astype(np.int64) % 2).reshape(-1, PAYLOAD_BITS)
    frac = votes.mean(axis=0)
    bits = (frac >= 0.5).astype(np.uint8)
    margin = float(np.mean(np.abs(frac - 0.5) * 2.0))
    return bits, margin


def extract_image(img: np.ndarray) -> np.ndarray:
    """Blind extraction: returns PAYLOAD_BITS bits (majority-voted)."""
    return _vote_bits(_coeffs(img))[0]


# Candidate inverse scales for geometric re-sync. Recovery only works when
# the trial dimensions are exact multiples of BLOCK, so all resizes snap.
_SCALES = np.unique(np.concatenate([
    np.arange(0.70, 1.41, 0.05),
    np.arange(0.87, 1.18, 0.005),
]))


def _balanced(bits: np.ndarray) -> bool:
    """A real signed payload has ~50% ones; degenerate reads collapse to 0%/100%."""
    frac = float(bits.mean())
    return 0.35 <= frac <= 0.65


def _read(im: np.ndarray):
    coeffs = _coeffs(im)
    bits, margin = _vote_bits(coeffs)
    conf = _lattice_confidence(coeffs)
    parity = parity_score_from_bits(bits)
    return bits, conf, parity, margin


def _sharpen(img: np.ndarray, amount: float) -> np.ndarray:
    blurred = cv2.GaussianBlur(img, (0, 0), 1.0)
    return cv2.addWeighted(img, 1.0 + amount, blurred, -amount, 0)


def extract_robust(img: np.ndarray) -> np.ndarray:
    """Extraction with geometric re-sync and de-blur fallbacks.

    Trust the direct read when the payload is self-consistent (parity),
    on-grid (lattice confidence), and looks like real signed data
    (balanced bits). Otherwise search candidate inverse scales — always
    resizing to exact block multiples, because the 8x8 grid only
    re-aligns then — over raw and sharpened variants, keeping the
    balanced, self-consistent candidate closest to the QIM grid.
    """
    bits, conf, parity, margin = _read(img)
    if parity >= 0.95 and conf >= 0.5 and _balanced(bits):
        return bits

    best = (bits, -1.0)
    h, w = img.shape[:2]
    for variant in (img, _sharpen(img, 0.5), _sharpen(img, 1.5)):
        for s in _SCALES:
            nw = int(round(w / s)) // BLOCK * BLOCK
            nh = int(round(h / s)) // BLOCK * BLOCK
            if nw < BLOCK * 2 or nh < BLOCK * 2:
                continue
            cand_img = variant if (nw, nh) == (w // BLOCK * BLOCK, h // BLOCK * BLOCK) and s == 1.0 \
                else cv2.resize(variant, (nw, nh), interpolation=cv2.INTER_CUBIC)
            c_bits, c_conf, c_parity, _ = _read(cand_img)
            if c_parity >= 0.9 and _balanced(c_bits) and c_conf > best[1]:
                best = (c_bits, c_conf)
            if best[1] >= 0.8 and c_parity >= 0.99:
                return best[0]
    return best[0]


def embed(image_path: str, out_path: str, payload_bits: np.ndarray) -> str:
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(image_path)
    out = embed_image(img, payload_bits)
    cv2.imwrite(out_path, out)
    return out_path


def extract(image_path: str) -> np.ndarray:
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(image_path)
    return extract_robust(img)
