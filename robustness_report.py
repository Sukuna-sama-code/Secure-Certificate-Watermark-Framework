"""Robustness report: attack a watermarked certificate and measure survival.

Usage:
    python robustness_report.py [--image samples/cert_watermarked.png]
                                [--content samples/content.txt]
                                [--out robustness_report.md]

For each attack it reports:
  - BER      : bit error rate of the extracted payload vs the embedded one
  - parity   : fraction of parity bits that still match (extraction health)
  - verdict  : AUTHENTIC / TAMPERED / FORGED
"""
import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from watermark import embed as wm_embed
from watermark import keys, payload as wm_payload


def _ber(a: np.ndarray, b: np.ndarray) -> float:
    n = min(len(a), len(b))
    return float(np.mean(a[:n] != b[:n]))


def attacks(img: np.ndarray):
    """Yield (name, attacked_image)."""
    tmp = "samples/_attack_tmp.jpg"
    for q in (95, 85, 70, 50):
        cv2.imwrite(tmp, img, [cv2.IMWRITE_JPEG_QUALITY, q])
        yield f"JPEG quality {q}", cv2.imread(tmp)
    os.remove(tmp)

    rng = np.random.default_rng(0)
    for sigma in (2, 4, 8):
        noisy = img.astype(np.float32) + rng.normal(0, sigma, img.shape)
        yield f"Gaussian noise sigma={sigma}", np.clip(noisy, 0, 255).astype(np.uint8)

    yield "Gaussian blur 3x3 s=0.8", cv2.GaussianBlur(img, (3, 3), 0.8)
    yield "Gaussian blur 5x5 s=1.2", cv2.GaussianBlur(img, (5, 5), 1.2)

    for f in (0.9, 0.98, 1.02, 1.1):
        r = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_LINEAR)
        yield f"Resize {f}x", r

    for delta in (-30, 30):
        bright = np.clip(img.astype(np.int16) + delta, 0, 255).astype(np.uint8)
        yield f"Brightness {delta:+d}", bright

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    yield "Grayscale conversion", cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default="samples/cert_watermarked.png")
    ap.add_argument("--content", default="samples/content.txt")
    ap.add_argument("--out", default="robustness_report.md")
    args = ap.parse_args()

    priv = keys.load_private_key()
    pub = keys.load_public_key()
    cert = open(args.content, "rb").read()
    embedded = wm_payload.build_payload(cert, priv)

    img = cv2.imread(args.image)
    if img is None:
        sys.exit(f"cannot read {args.image}")

    rows = []
    for name, attacked in attacks(img):
        tmp = "samples/_attack_tmp.png"
        cv2.imwrite(tmp, attacked)
        bits = wm_embed.extract(tmp)
        os.remove(tmp)
        result = wm_payload.verify_payload(bits, pub, cert)
        rows.append((name, _ber(embedded, bits), result["parity_score"], result["verdict"]))
        print(f"{name:26s} BER={_ber(embedded, bits):.4f}  parity={result['parity_score']:.3f}  {result['verdict']}")

    lines = ["| Attack | Bit error rate | Parity score | Verdict |",
             "|---|---|---|---|"]
    for name, ber, parity, verdict in rows:
        lines.append(f"| {name} | {ber:.4f} | {parity:.3f} | {verdict} |")
    with open(args.out, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nMarkdown table written to {args.out}")


if __name__ == "__main__":
    main()
