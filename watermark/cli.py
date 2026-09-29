"""CLI: issue (embed watermark) and verify (extract + check) certificates."""
import argparse
import os
import sys

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from watermark import embed as wm_embed
from watermark import keys, payload as wm_payload


def cmd_issue(args):
    priv = keys.load_private_key()
    with open(args.content, "rb") as f:
        cert_bytes = f.read()
    bits = wm_payload.build_payload(cert_bytes, priv)
    out = wm_embed.embed(args.image, args.out, bits)
    print(f"Watermarked certificate written to: {out}")


def cmd_verify(args):
    pub = keys.load_public_key()
    with open(args.content, "rb") as f:
        cert_bytes = f.read()
    bits = wm_embed.extract(args.image)
    result = wm_payload.verify_payload(bits, pub, cert_bytes)
    print(f"Verdict: {result['verdict']}")
    print(f"  content hash OK:   {result['hash_ok']}")
    print(f"  signature OK:      {result['signature_ok']}")
    print(f"  parity score:      {result['parity_score']}")
    return 0 if result["verdict"] == "AUTHENTIC" else 1


def main():
    p = argparse.ArgumentParser(description="Certificate watermarking framework")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("issue", help="embed watermark into a certificate image")
    pi.add_argument("--image", required=True, help="original certificate image")
    pi.add_argument("--content", required=True, help="certificate content file (text/json/pdf bytes)")
    pi.add_argument("--out", required=True, help="output watermarked image path")

    pv = sub.add_parser("verify", help="verify a certificate image")
    pv.add_argument("--image", required=True, help="certificate image to verify")
    pv.add_argument("--content", required=True, help="certificate content file to check against")

    args = p.parse_args()
    if args.cmd == "issue":
        cmd_issue(args)
    else:
        sys.exit(cmd_verify(args))


if __name__ == "__main__":
    main()
