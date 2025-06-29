import fitz  # PyMuPDF
import json
import requests
import os
from io import BytesIO
from docx import Document
import streamlit as st

# === CONFIG ===
OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")

if not OPENROUTER_API_KEY:
    st.error("❌ OpenRouter API key not found. Add it in Streamlit → Settings → Secrets.")
    st.stop()

HTTP_REFERER = "https://your-app-name.streamlit.app"  # OPTIONAL: Your Streamlit Cloud app URL

# === STEP 1: Clean Unicode Text ===
def clean_text(text):
    return text.encode("utf-8", "ignore").decode("utf-8")

# === STEP 2: Extract PDF Text ===
def extract_pdf_text(uploaded_pdfs):
    combined_text = ""
    for file in uploaded_pdfs:
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            for page in doc:
                combined_text += page.get_text()
    return clean_text(combined_text)

# === STEP 3: Extract Placeholders from .docx Template ===
def extract_placeholders(docx_file):
    doc = Document(docx_file)
    placeholders = set()
    for para in doc.paragraphs:
        for word in para.text.split():
            if word.startswith("[") and word.endswith("]"):
                placeholders.add(word.strip("[]"))
    return list(placeholders)

# === STEP 4: Call LLM API to Fill Fields ===
def call_llm(pdf_text, placeholders):
    prompt = f"""
You are an insurance claim assistant. Extract values for the following placeholders:

{placeholders}

PDF Text:
\"\"\"
{pdf_text[:6000]}
\"\"\"

Return ONLY valid JSON in this format:
{{
  "DATE_LOSS": "2024-11-13",
  "INSURED_NAME": "Richard Daly",
  ...
}}
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
        body_json = json.dumps(body, ensure_ascii=False).encode("utf-8")
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, data=body_json)
        res.raise_for_status()
        data = res.json()
        raw_output = data["choices"][0]["message"]["content"]
        return json.loads(raw_output)
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ OpenRouter HTTP Error: {res.status_code} - {res.text}")
    except Exception as e:
        st.error(f"❌ LLM call failed: {e}")
    return {}

# === STEP 5: Mock Fallback Data ===
def mock_data():
    return {
        "DATE_LOSS": "2024-11-13",
        "INSURED_NAME": "Richard Daly",
        "MORTGAGE_CO": "Alacrity",
        "INSURED_H_STREET": "123 Storm Ln",
        "INSURED_H_CITY": "San Antonio",
        "INSURED_H_STATE": "TX",
        "INSURED_H_ZIP": "78265",
        "DATE_INSPECTED": "2024-11-14",
        "TOL_CODE": "wind",
        "DATE_RECEIVED": "2024-11-15",
        "MORTGAGEE": "Alacrity"
    }

# === STEP 6: Fill DOCX Template with Values ===
def fill_template(docx_file, field_values):
    doc = Document(docx_file)
    for para in doc.paragraphs:
        for key, val in field_values.items():
            if f"[{key}]" in para.text:
                para.text = para.text.replace(f"[{key}]", val)
    output = BytesIO()
    doc.save(output)
    output.seek(0)
    return output

# === STREAMLIT INTERFACE ===
st.set_page_config(page_title="GLR Report Filler", page_icon="📄")
st.title("📄 GLR Pipeline - Insurance Auto Filler")

template_file = st.file_uploader("Upload Template (.docx)", type=["docx"])
pdf_files = st.file_uploader("Upload Photo Reports (.pdf)", type=["pdf"], accept_multiple_files=True)

if st.button("Process"):
    if not template_file or not pdf_files:
        st.error("Please upload both the DOCX template and at least one PDF.")
        st.stop()

    with st.spinner("🔍 Extracting text from PDFs..."):
        pdf_text = extract_pdf_text(pdf_files)

    with st.spinner("🧠 Extracting placeholders..."):
        placeholders = extract_placeholders(template_file)

    with st.spinner("🤖 Calling LLM to fill values..."):
        field_values = call_llm(pdf_text, placeholders)
        if not field_values:
            st.warning("⚠️ LLM failed, using mock data instead.")
            field_values = mock_data()

    st.success("✅ Fields extracted successfully!")

    with st.spinner("📝 Filling template..."):
        filled_doc = fill_template(template_file, field_values)

    st.download_button(
        label="📥 Download Filled Report",
        data=filled_doc,
        file_name="filled_report.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
