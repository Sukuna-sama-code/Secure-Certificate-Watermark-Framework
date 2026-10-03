"""Streamlit web app: issue and verify watermarked certificates in the browser.

Run with:  streamlit run app.py
"""
import cv2
import numpy as np
import streamlit as st

from watermark import embed as wm_embed
from watermark import keys, payload as wm_payload

st.set_page_config(
    page_title="Certificate Watermark Verifier",
    page_icon="🎓",
    layout="centered",
)

# ---------------------------------------------------------------- styling
import streamlit as st
st.markdown("""
<style>
/* 1. Base Gradient Background (Mean Fruit) */
.stApp {
    background: linear-gradient(135deg, #fccb90 0%, #d57eeb 100%) !important;
    background-size: cover;
    background-attachment: fixed;
}

/* 2. Main Glass Card Container - Soft & Clean */
div[data-testid="stVerticalBlock"] > div:has(div[data-testid="stFileUploader"]) {
    background: rgba(255, 255, 255, 0.5) !important;
    border: 1px solid rgba(255, 255, 255, 0.8) !important;
    border-radius: 20px !important;
    padding: 2.5rem !important;
    box-shadow: 0 12px 40px 0 rgba(213, 126, 235, 0.25) !important; /* Soft purple shadow */
    backdrop-filter: blur(16px) !important;
    -webkit-backdrop-filter: blur(16px) !important;
}

/* 3. Global Text - Deep Eggplant/Magenta for Readability */
.stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp label, .stApp span, div[data-testid="stMarkdownContainer"] p {
    color: #4a044e !important;
    font-weight: 500;
}

/* 4. Clean Modern Tabs */
button[data-baseweb="tab"] {
    color: #86198f !important;
    background-color: transparent !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #4a044e !important;
    border-bottom-color: #d57eeb !important; /* Matches gradient end */
    font-weight: 700 !important;
}

/* 5. FIX THE STUBBORN BLACK UPLOADER BOXES */
[data-testid="stFileUploadDropzone"] {
    background-color: rgba(255, 255, 255, 0.65) !important; 
    border: 2px dashed #d57eeb !important; /* Pastel purple dashed border */
    border-radius: 12px !important;
    padding: 2rem !important;
    transition: all 0.3s ease !important;
}
[data-testid="stFileUploadDropzone"]:hover {
    background-color: rgba(255, 255, 255, 0.9) !important;
    border-color: #c026d3 !important;
}

/* Force inner text and icons to be dark purple (fixes black boxes) */
[data-testid="stFileUploadDropzone"] *, 
[data-testid="stFileUploadDropzone"] div, 
[data-testid="stFileUploadDropzone"] span, 
[data-testid="stFileUploadDropzone"] small {
    background-color: transparent !important;
    color: #4a044e !important; 
}
[data-testid="stFileUploadDropzone"] svg {
    fill: #4a044e !important; 
}

/* Style the internal "Browse files" button */
[data-testid="stFileUploadDropzone"] button {
    background-color: #ffffff !important;
    border: 1px solid #d57eeb !important;
    color: #4a044e !important;
    border-radius: 8px !important;
}

/* 6. STYLE THE MAIN PRIMARY BUTTONS (Vibrant Purple + Pure White Text) */
div[data-testid="stButton"] button {
    background: linear-gradient(135deg, #d57eeb 0%, #a21caf 100%) !important; /* Pastel purple to rich fuchsia */
    border: none !important; 
    border-radius: 12px !important;
    padding: 0.75rem 2.5rem !important;
    box-shadow: 0 6px 20px rgba(162, 28, 175, 0.4) !important;
    transition: all 0.3s ease !important;
}

/* Ensure the text inside the main button is purely white */
div[data-testid="stButton"] button, 
div[data-testid="stButton"] button p, 
div[data-testid="stButton"] button span {
    color: #ffffff !important;
    font-weight: 600 !important;
    letter-spacing: 0.5px !important;
}

/* Hover effect: Glows brighter */
div[data-testid="stButton"] button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(162, 28, 175, 0.6) !important;
}
</style>
""", unsafe_allow_html=True)
# ---------------------------------------------------------------- keys
priv = keys.load_private_key()
pub = keys.load_public_key()


def _decode(uploaded) -> np.ndarray:
    data = np.frombuffer(uploaded.getvalue(), np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        st.error("Could not read that file as an image. Upload a PNG or JPG.")
        st.stop()
    return img


def _content_bytes() -> bytes:
    if st.session_state.content_mode == "Upload a file":
        if st.session_state.content_file is None:
            st.warning("Upload a content file first.")
            st.stop()
        return st.session_state.content_file.getvalue()
    return st.session_state.content_text.encode("utf-8")


VERDICTS = {
    "AUTHENTIC": ("ok", "Authentic", "The signature is valid and the content matches this certificate."),
    "TAMPERED": ("warn", "Tampered", "The signature is valid, but the content differs from what was signed."),
    "FORGED": ("bad", "Forged", "No valid watermark was found in this image."),
}

tab_issue, tab_verify = st.tabs(["Issue a certificate", "Verify a certificate"])

# ---------------------------------------------------------------- issue
with tab_issue:
    st.subheader("Issue a watermarked certificate")
    st.write("Upload the certificate image and its content. The watermark is added without visible changes.")
    img_up = st.file_uploader(
        "Certificate image (PNG works best)",
        type=["png", "jpg", "jpeg"],
        key="img_issue",
    )
    st.radio("Certificate content", ["Upload a file", "Type the text"], key="content_mode", horizontal=True)
    if st.session_state.content_mode == "Upload a file":
        st.file_uploader("Content file (txt, pdf, ...)", key="content_file")
    else:
        st.text_area(
            "Content text",
            key="content_text",
            value="Jane Doe\nCourse: Secure Watermarking 101\nDate: 2026-09-29\n",
        )
    if st.button("Embed watermark", type="primary") and img_up is not None:
        img = _decode(img_up)
        bits = wm_payload.build_payload(_content_bytes(), priv)
        out = wm_embed.embed_image(img, bits)
        mse = np.mean((img.astype(np.float32) - out.astype(np.float32)) ** 2)
        psnr = 10 * np.log10(255 ** 2 / mse) if mse > 0 else float("inf")
        ok, buf = cv2.imencode(".png", out)
        st.success("Watermark embedded. Download the certificate below.")
        before, after = st.columns(2)
        before.image(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), caption="Original", use_container_width=True)
        after.image(
            cv2.cvtColor(out, cv2.COLOR_BGR2RGB),
            caption=f"Watermarked (PSNR {psnr:.1f} dB)",
            use_container_width=True,
        )
        st.download_button(
            "Download watermarked certificate",
            buf.tobytes(),
            file_name="certificate_watermarked.png",
            mime="image/png",
        )
    elif img_up is None:
        st.caption("Upload a certificate image to get started.")

# ---------------------------------------------------------------- verify
with tab_verify:
    st.subheader("Verify a certificate")
    st.write("Upload the certificate image and the content it should match.")
    vimg = st.file_uploader(
        "Certificate image to check",
        type=["png", "jpg", "jpeg"],
        key="img_verify",
    )
    st.radio("Certificate content", ["Upload a file", "Type the text"], key="content_mode_v", horizontal=True)
    if st.session_state.content_mode_v == "Upload a file":
        cfile = st.file_uploader("Content file (txt, pdf, ...)", key="content_file_v")
        cert_bytes = cfile.getvalue() if cfile else None
    else:
        ctext = st.text_area("Content text", key="content_text_v")
        cert_bytes = ctext.encode("utf-8") if ctext else None

    if st.button("Verify certificate", type="primary"):
        if vimg is None or cert_bytes is None:
            st.warning("Add both the certificate image and its content, then verify.")
        else:
            img = _decode(vimg)
            bits = wm_embed.extract_robust(img)
            result = wm_payload.verify_payload(bits, pub, cert_bytes)
            cls, label, text = VERDICTS[result["verdict"]]
            st.markdown(
                f"""
<div class="stamp-wrap">
  <div class="stamp {cls}">{label}</div>
  <div class="stamp-text">{text}</div>
</div>
""",
                unsafe_allow_html=True,
            )
            with st.expander("Technical details"):
                st.json(result)
