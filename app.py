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
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=Instrument+Sans:wght@400;500;600&display=swap');

:root {
  --ink: #0F3D3E;
  --ink-soft: #2C5859;
  --brass: #B08D3C;
  --paper: #F3F5F4;
  --line: #D5DBD9;
  --ok: #1E7A4C;
  --warn: #B26A00;
  --bad: #B3261E;
}

html, body, [class*="css"], .stApp {
  font-family: 'Instrument Sans', system-ui, sans-serif;
}
.stApp { background: var(--paper); color: #17302F; }
#MainMenu, footer, header [data-testid="stToolbar"] { visibility: hidden; }
.block-container { padding-top: 1.5rem; max-width: 760px; }

/* hero */
.hero {
  background: var(--ink);
  color: #F3F5F4;
  border-radius: 14px;
  padding: 2.2rem 2rem 2rem 2rem;
  margin-bottom: 1.2rem;
  border-bottom: 5px solid var(--brass);
}
.hero h1 {
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 700;
  font-size: 2.15rem;
  line-height: 1.15;
  margin: 0 0 .6rem 0;
  color: #F3F5F4;
  letter-spacing: -0.01em;
}
.hero p {
  margin: 0;
  max-width: 56ch;
  color: #C9D8D6;
  font-size: 1.02rem;
  line-height: 1.55;
}

/* verdict legend */
.legend { display: flex; gap: .6rem; flex-wrap: wrap; margin-bottom: 1.4rem; }
.legend div {
  flex: 1 1 200px;
  background: #fff;
  border: 1px solid var(--line);
  border-left-width: 4px;
  border-radius: 6px;
  padding: .65rem .8rem;
  font-size: .9rem;
  line-height: 1.4;
}
.legend b { display: block; margin-bottom: .1rem; }
.legend .l-ok { border-left-color: var(--ok); }
.legend .l-warn { border-left-color: var(--warn); }
.legend .l-bad { border-left-color: var(--bad); }

/* tabs */
.stTabs [data-baseweb="tab-list"] { gap: 1.6rem; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] { font-weight: 600; padding: .6rem 0; color: var(--ink-soft); }
.stTabs [aria-selected="true"] { color: var(--ink); }
.stTabs [data-baseweb="tab-highlight"] { background: var(--brass); height: 3px; }

h2, h3 { font-family: 'Fraunces', Georgia, serif; color: var(--ink); }

/* buttons */
.stButton > button[kind="primary"], .stDownloadButton > button {
  background: var(--ink);
  color: #fff;
  border: 0;
  border-radius: 8px;
  padding: .55rem 1.4rem;
  font-weight: 600;
}
.stButton > button[kind="primary"]:hover, .stDownloadButton > button:hover {
  background: var(--ink-soft);
  color: #fff;
}
.stButton > button:focus-visible, .stDownloadButton > button:focus-visible {
  outline: 3px solid var(--brass);
  outline-offset: 2px;
}

/* uploader */
[data-testid="stFileUploaderDropzone"] {
  background: #fff;
  border: 1.5px dashed #9FB0AD;
  border-radius: 10px;
}

/* verdict stamp */
.stamp-wrap { display: flex; align-items: center; gap: 1.2rem; margin: 1rem 0 .6rem 0; }
.stamp {
  width: 128px; height: 128px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center; text-align: center;
  font-family: 'Fraunces', Georgia, serif; font-weight: 700;
  font-size: 1.05rem; line-height: 1.1;
  border: 4px double currentColor;
  outline: 2px solid currentColor; outline-offset: 4px;
  transform: rotate(-6deg);
  background: #fff;
  flex: 0 0 auto;
}
.stamp.ok { color: var(--ok); }
.stamp.warn { color: var(--warn); }
.stamp.bad { color: var(--bad); }
.stamp-text { font-size: 1.02rem; line-height: 1.5; max-width: 40ch; }

@media (max-width: 560px) {
  .hero h1 { font-size: 1.7rem; }
  .stamp-wrap { flex-direction: column; align-items: flex-start; }
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="hero">
  <h1>Secure Certificate Watermark Framework</h1>
  <p>Issue certificates with an invisible, signed watermark, then check later
  whether a certificate is genuine, edited, or fake.</p>
</div>
<div class="legend">
  <div class="l-ok"><b>Authentic</b>Valid signature and the content matches.</div>
  <div class="l-warn"><b>Tampered</b>Valid signature, but the content was changed.</div>
  <div class="l-bad"><b>Forged</b>No valid watermark found.</div>
</div>
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
