import fitz, json, requests, os
from io import BytesIO
from docx import Document
import streamlit as st

# ▸ 1 – Get the key safely
OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    st.error("❌  OpenRouter API key not found.  Add it in Settings ➜ Secrets.")
    st.stop()

# ▸ 2 – Tell OpenRouter where the call is coming from (use your own URL in prod)
HTTP_REFERER = "https://your‑app‑name.streamlit.app"

# ---------- helper functions ----------
def extract_pdf_text(uploaded_pdfs):
    txt = ""
    for f in uploaded_pdfs:
        with fitz.open(stream=f.read(), filetype="pdf") as doc:
            for p in doc:
                txt += p.get_text()
    return txt

def extract_placeholders(docx_file):
    doc = Document(docx_file)
    ph = set()
    for para in doc.paragraphs:
        for w in para.text.split():
            if w.startswith("[") and w.endswith("]"):
                ph.add(w.strip("[]"))
    return list(ph)

import json

def call_llm(pdf_text, placeholders):
    prompt = f"""
You are an insurance claim assistant. Extract values for the following placeholders:

{placeholders}

PDF Text:
\"\"\"
{pdf_text[:6000]}
\"\"\"

Return ONLY valid JSON.
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": HTTP_REFERER
    }

    body = {
        "model": "mistralai/mixtral-8x7b",
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8")  # 💡 This forces correct encoding
        )
        res.raise_for_status()
        data = res.json()
        raw = data["choices"][0]["message"]["content"]
        return json.loads(raw)
    except requests.exceptions.HTTPError as e:
        st.error(f"OpenRouter error ({res.status_code}): {res.text}")
    except Exception as e:
        st.error(f"LLM call failed: {e}")
    return {}


def mock_values():
    return {
        "DATE_LOSS": "2024‑11‑13",
        "INSURED_NAME": "Richard Daly",
        "MORTGAGE_CO": "Alacrity",
        "INSURED_H_STREET": "123 Storm Ln",
        "INSURED_H_CITY": "San Antonio",
        "INSURED_H_STATE": "TX",
        "INSURED_H_ZIP": "78265",
        "DATE_INSPECTED": "2024‑11‑14"
    }

def fill_template(src_docx, values):
    doc = Document(src_docx)
    for p in doc.paragraphs:
        for k, v in values.items():
            p.text = p.text.replace(f"[{k}]", v)
    out = BytesIO()
    doc.save(out)
    out.seek(0)
    return out
# ---------- Streamlit UI ----------
st.set_page_config("GLR Filler", "📝")
st.title("📄  GLR Pipeline – Auto‑Fill Insurance Template")

tpl = st.file_uploader("Template (.docx)", type=["docx"])
pdfs = st.file_uploader("Photo reports (.pdf)", type=["pdf"], accept_multiple_files=True)

if st.button("Process"):
    if not tpl or not pdfs:
        st.error("Upload both a template and at least one PDF.")
        st.stop()

    with st.spinner("Extracting PDF text…"):
        text = extract_pdf_text(pdfs)

    with st.spinner("Finding placeholders…"):
        ph = extract_placeholders(tpl)

    with st.spinner("Calling LLM…"):
        values = call_llm(text, ph) or mock_values()

    st.success("Placeholders filled!")
    filled = fill_template(tpl, values)

    st.download_button("📥 Download filled report",
                       data=filled,
                       file_name="filled_report.docx",
                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
