# Robustness: Phase 3 (baseline) vs Phase 4 (re-sync extractor)

Phase 4 changes: majority-vote decoding across the ~30 repeated payload copies,
block-aligned inverse-scale search (geometric re-sync), sharpening variants for blur,
and degenerate-payload rejection (bit-balance + lattice confidence).

| Attack | BER before | Verdict before | BER after | Verdict after |
|---|---|---|---|---|
| JPEG quality 95 | 0.0000 | AUTHENTIC | 0.0000 | AUTHENTIC |
| JPEG quality 85 | 0.0000 | AUTHENTIC | 0.0000 | AUTHENTIC |
| JPEG quality 70 | 0.0000 | AUTHENTIC | 0.0000 | AUTHENTIC |
| JPEG quality 50 | 0.5111 | FORGED | 0.5111 | FORGED |
| Gaussian noise sigma=2 | 0.0000 | AUTHENTIC | 0.0000 | AUTHENTIC |
| Gaussian noise sigma=4 | 0.0000 | AUTHENTIC | 0.0000 | AUTHENTIC |
| Gaussian noise sigma=8 | 0.0208 | FORGED | 0.0000 | AUTHENTIC |
| Gaussian blur 3x3 s=0.8 | 0.5111 | FORGED | 0.0000 | AUTHENTIC |
| Gaussian blur 5x5 s=1.2 | 0.5111 | FORGED | 0.5111 | FORGED |
| Resize 0.9x | 0.5111 | FORGED | 0.0000 | AUTHENTIC |
| Resize 0.98x | 0.5097 | FORGED | 0.0000 | AUTHENTIC |
| Resize 1.02x | 0.5000 | FORGED | 0.0000 | AUTHENTIC |
| Resize 1.1x | 0.5111 | FORGED | 0.0000 | AUTHENTIC |
| Brightness -30 | 0.0000 | AUTHENTIC | 0.0000 | AUTHENTIC |
| Brightness +30 | 0.5097 | FORGED | 0.5111 | FORGED |
| Grayscale conversion | 0.0000 | AUTHENTIC | 0.0000 | AUTHENTIC |

Survived 7/16 attacks before, 13/16 after.

Remaining failures are information-destroying attacks:
- Blur 5x5 s=1.2 removes the (4,3) mid-frequency coefficient entirely (unrecoverable).
- Brightness +30 clips 97% of pixels on this mostly-white certificate.
- JPEG q=50 quantization step exceeds the QIM step Q=24 at that coefficient.
