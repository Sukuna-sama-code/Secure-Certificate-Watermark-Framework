"""Streamlit web app: issue and verify watermarked certificates in the browser.

Run with:  streamlit run app.py
"""
import cv2
import numpy as np
import streamlit as st

from watermark import embed as wm_embed
from watermark import keys, payload as wm_payload

st.set_page_config(page_title="Certificate Watermark Verifier", page_icon="🎓")
st.title("Secure Certificate Watermark Framework")
st.caption("Invisible DCT watermark + Ed25519 signature. "
           "AUTHENTIC = valid signature & matching content hash; "
           "TAMPERED = valid signature but content changed; "
           "FORGED = no valid watermark.")

priv = keys.load_private_key()
pub = keys.load_public_key()


def _decode(uploaded) -> np.ndarray:
    data = np.frombuffer(uploaded.getvalue(), np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        st.error("Could not read that file as an image.")
        st.stop()
    return img


def _content_bytes() -> bytes:
    if st.session_state.content_mode == "Upload a file":
        if st.session_state.content_file is None:
            st.warning("Upload a content file first.")
            st.stop()
        return st.session_state.content_file.getvalue()
    return st.session_state.content_text.encode("utf-8")


tab_issue, tab_verify = st.tabs(["Issue (embed watermark)", "Verify certificate"])

with tab_issue:
    st.subheader("Issue a watermarked certificate")
    img_up = st.file_uploader("Certificate image (PNG recommended)", type=["png", "jpg", "jpeg"], key="img_issue")
    st.radio("Certificate content", ["Upload a file", "Type the text"], key="content_mode")
    if st.session_state.content_mode == "Upload a file":
        st.file_uploader("Content file (txt/pdf/...)", key="content_file")
    else:
        st.text_area("Content text", key="content_text",
                     value="Jane Doe\nCourse: Secure Watermarking 101\nDate: 2026-09-29\n")
    if st.button("Embed watermark", type="primary") and img_up is not None:
        img = _decode(img_up)
        bits = wm_payload.build_payload(_content_bytes(), priv)
        out = wm_embed.embed_image(img, bits)
        mse = np.mean((img.astype(np.float32) - out.astype(np.float32)) ** 2)
        psnr = 10 * np.log10(255 ** 2 / mse) if mse > 0 else float("inf")
        ok, buf = cv2.imencode(".png", out)
        st.image(cv2.cvtColor(out, cv2.COLOR_BGR2RGB), caption=f"Watermarked (PSNR {psnr:.1f} dB)")
        st.download_button("Download watermarked certificate", buf.tobytes(),
                           file_name="certificate_watermarked.png", mime="image/png")

with tab_verify:
    st.subheader("Verify a certificate")
    vimg = st.file_uploader("Certificate image to check", type=["png", "jpg", "jpeg"], key="img_verify")
    st.radio("Certificate content", ["Upload a file", "Type the text"], key="content_mode_v")
    if st.session_state.content_mode_v == "Upload a file":
        cfile = st.file_uploader("Content file (txt/pdf/...)", key="content_file_v")
        cert_bytes = cfile.getvalue() if cfile else None
    else:
        ctext = st.text_area("Content text", key="content_text_v")
        cert_bytes = ctext.encode("utf-8") if ctext else None

    if st.button("Verify", type="primary") and vimg is not None and cert_bytes is not None:
        img = _decode(vimg)
        bits = wm_embed.extract_robust(img)
        result = wm_payload.verify_payload(bits, pub, cert_bytes)
        color = {"AUTHENTIC": "green", "TAMPERED": "orange", "FORGED": "red"}[result["verdict"]]
        st.markdown(f"### :{color}[{result['verdict']}]")
        st.json(result)
