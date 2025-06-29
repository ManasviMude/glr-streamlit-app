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
    st.error("❌ OpenRouter API key not found. Add it in Streamlit > Settings > Secrets.")
    st.stop()

HTTP_REFERER = "https://your-app-name.streamlit.app"  # Change this to your deployed app URL if needed

# === CLEAN UNICODE TEXT ===
def clean_text(text):
    return text.encode("utf-8", "ignore").decode("utf-8")

# === PDF TEXT EXTRACTION ===
def extract_pdf_text(uploaded_pdfs):
    combined_text = ""
    for file in uploaded_pdfs:
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            for page in doc:
                combined_text += page.get_text()
    return clean_text(combined_text)

# === PLACEHOLDER EXTRACTION FROM DOCX ===
def extract_placeholders(docx_file):
    doc = Document(docx_file)
    placeholders = set()
    for para in doc.paragraphs:
        for word in para.text.split():
            if word.startswith("[") and word.endswith("]"):
                placeholders.add(word.strip("[]"))
    return list(placeholders)

# === CALL LLM TO FILL PLACEHOLDERS ===
def call_llm(pdf_text, placeholders):
    prompt = f"""
You are an insurance claim assistant. From the report text below, extract values for the following fields (placeholders):

{placeholders}

Text:
\"\"\"
{pdf_text[:6000]}
\"\"\"

Return ONLY valid JSON like this:
{{
  "XM8_CLAIM_NUM": "123456",
  "XM8_INSURED_NAME": "James Wade",
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
        encoded_body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, data=encoded_body)
        res.raise_for_status()
        content = res.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        st.error(f"❌ LLM call failed: {e}")
        return {}

# === FALLBACK DATA FOR DEMO ===
def mock_data():
    return {
        "XM8_CLAIM_NUM": "WJ-789456",
        "XM8_INSURED_NAME": "James Wade",
        "XM8_FILE_NO": "ELV-112233",
        "XM8_DATE_LOSS": "2024-11-21",
        "XM8_INSURED_P_STREET": "7061 Springfield Hills Dr. S.",
        "XM8_INSURED_P_CITY": "Indianapolis",
        "XM8_INSURED_P_STATE": "IN",
        "XM8_INSURED_P_ZIP": "46229",
        "XM8_DATE_INSPECTED": "2024-11-26",
        "XM8_CLAIM_REP_NAME": "Steven Kujawski",
        "XM8_REFERENCE_COMPANY": "Wayne Mutual Insurance Company",
        "XM8_ESTIMATOR_NAME": "Steven Kujawski",
        "XM8_ESTIMATOR_E_MAIL": "claims@elevateclaims.com",
        "XM8_ESTIMATOR_C_PHONE": "317-973-7676"
    }

# === FILL TEMPLATE WITH EXTRACTED VALUES ===
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

# === STREAMLIT APP ===
st.set_page_config("Elevate Claims Auto-Filler", page_icon="📄")
st.title("📄 XM8 Report Auto-Filler – Elevate Claims")

template_file = st.file_uploader("Upload XM8 Template (.docx)", type=["docx"])
pdf_files = st.file_uploader("Upload Photo Reports (.pdf)", type=["pdf"], accept_multiple_files=True)

if st.button("Process"):
    if not template_file or not pdf_files:
        st.error("Please upload both the DOCX template and at least one PDF report.")
    else:
        with st.spinner("🔍 Extracting PDF text..."):
            text = extract_pdf_text(pdf_files)

        with st.spinner("🔎 Extracting placeholders..."):
            placeholders = extract_placeholders(template_file)

        with st.spinner("🤖 Querying LLM..."):
            field_values = call_llm(text, placeholders)
            if not field_values:
                st.warning("⚠️ Using mock data due to LLM failure.")
                field_values = mock_data()

        st.success("✅ Data extracted and ready!")

        with st.spinner("📝 Generating filled document..."):
            filled_doc = fill_template(template_file, field_values)

        st.download_button(
            label="📥 Download Filled XM8 Report",
            data=filled_doc,
            file_name="filled_xm8_report.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
