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


import streamlit as st

st.markdown("""
<style>
/* Force Deep Blue text across the entire site */
.stApp, 
.stApp p, 
.stApp h1, 
.stApp h2, 
.stApp h3, 
.stApp label, 
.stApp span, 
div[data-testid="stMarkdownContainer"] p {
    color: #0f172a !important;
    font-weight: 500;
}

/* 2. Main Glass Card Container */
div[data-testid="stVerticalBlock"] > div:has(div[data-testid="stFileUploader"]) {
    background: rgba(255, 255, 255, 0.45) !important;
    border: 1px solid rgba(255, 255, 255, 0.7) !important;
    border-radius: 20px !important;
    padding: 2rem !important;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.08) !important;
    backdrop-filter: blur(20px) !important;
}

/* 3. High-Contrast Dark Text */
.stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp label, .stApp span {
    color: #1e1b4b !important;
    font-weight: 500;
}

/* 4. Fix Black Uploader Box -> Frosted Glass Box */
div[data-testid="stFileUploader"] {
    background: rgba(255, 255, 255, 0.6) !important;
    border: 2px dashed rgba(120, 80, 160, 0.35) !important;
    border-radius: 14px !important;
    padding: 1.2rem !important;
    transition: all 0.3s ease !important;
}

div[data-testid="stFileUploader"]:hover {
    background: rgba(255, 255, 255, 0.85) !important;
    border-color: #8b5cf6 !important;
}

/* Target internal Streamlit uploader elements to strip dark default fills */
div[data-testid="stFileUploader"] section {
    background-color: transparent !important;
}

/* 5. Tabs Styling */
button[data-baseweb="tab"] {
    color: #475569 !important;
    font-weight: 600 !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    color: #6d28d9 !important;
    border-bottom-color: #6d28d9 !important;
}

/* 6. Primary Action Button ("Embed watermark") */
/* Primary Action Button ("Embed watermark" / "Verify certificate") */
.stButton > button {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%) !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.6rem 1.5rem !important;
    box-shadow: 0 6px 20px rgba(79, 70, 229, 0.35) !important;
    transition: all 0.3s ease !important;
}

/* Force pure white text specifically on button text and internal elements */
.stButton > button, 
.stButton > button p, 
.stButton > button span {
    color: #ffffff !important;
    font-weight: 600 !important;
}

.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(79, 70, 229, 0.5) !important;
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
