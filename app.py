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


st.markdown(
    """
    <style>
    /* Deep Rich Tech Background with Subtle Glow Effect */
    .stApp {
    background-image: linear-gradient(to right, #ff8177 0%, #ff8c7f 21%, #f99185 52%, #cf556c 78%, #b12a5b 100%);
    background-size: cover;
    background-attachment: fixed;
    color: #ffffff;
}
    /* Force high-contrast text */
    .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp label, .stApp span {
        color: #f1f5f9 !important;
    }

    /* Glassmorphic Container Cards for Uploader & Sections */
    div[data-testid="stVerticalBlock"] > div:has(div[data-testid="stFileUploader"]) {
    background: rgba(120, 30, 60, 0.35); /* Rich translucent berry/plum tone */
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 16px;
    padding: 1.5rem;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.25);
    backdrop-filter: blur(12px);
}

    /* File Uploader Customization */
    /* File Uploader Customization */
    div[data-testid="stFileUploader"] {
    background-color: rgba(80, 20, 45, 0.35);
    border: 2px dashed rgba(255, 255, 255, 0.25);
    border-radius: 12px;
    padding: 1rem;
    transition: all 0.3s ease;
}

    div[data-testid="stFileUploader"]:hover {
    border-color: #ff8177;
    background-color: rgba(100, 25, 55, 0.55);
}
    /* Tabs Styling */
    button[data-baseweb="tab"] {
        color: #94a3b8 !important;
        font-weight: 600;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #38bdf8 !important;
        border-bottom-color: #38bdf8 !important;
    }

    /* Modern Gradient Primary Action Button */
    .stButton > button {
        background: linear-gradient(135deg, #38bdf8 0%, #2563eb 100%);
        color: #ffffff !important;
        border: none;
        border-radius: 10px;
        font-weight: 600;
        padding: 0.6rem 1.2rem;
        box-shadow: 0 4px 20px rgba(56, 189, 248, 0.3);
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, #0ea5e9 0%, #1d4ed8 100%);
        box-shadow: 0 6px 24px rgba(56, 189, 248, 0.5);
        transform: translateY(-1px);
    }
    </style>
    """,
    unsafe_allow_html=True,
)
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
