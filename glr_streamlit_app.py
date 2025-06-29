import fitz
import json
import requests
from io import BytesIO
from docx import Document
import streamlit as st

# ✅ Use secret for OpenRouter API key (set in Streamlit Cloud > Settings > Secrets)
OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]

# === STEP 1: Extract PDF text ===
def extract_pdf_text(uploaded_pdfs):
    combined_text = ""
    for file in uploaded_pdfs:
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            for page in doc:
                combined_text += page.get_text()
    return combined_text

# === STEP 2: Extract placeholders from DOCX ===
def extract_placeholders(docx_file):
    doc = Document(docx_file)
    placeholders = set()
    for para in doc.paragraphs:
        for word in para.text.split():
            if word.startswith("[") and word.endswith("]"):
                placeholders.add(word.strip("[]"))
    return list(placeholders)

# === STEP 3: Call OpenRouter LLM ===
def call_llm(pdf_text, placeholders):
    prompt = f"""
You are an insurance claim assistant. Extract values for the following placeholders:

{placeholders}

Text:
\"\"\"
{pdf_text[:6000]}
\"\"\"

Return only valid JSON. Example:
{{
  "DATE_LOSS": "2024-11-13",
  "INSURED_NAME": "Richard Daly",
  ...
}}
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    body = {
        "model": "mistralai/mixtral-8x7b",
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=body)
        res.raise_for_status()
        data = res.json()
        if 'choices' in data:
            return json.loads(data['choices'][0]['message']['content'])
        else:
            return {}
    except Exception as e:
        st.warning(f"⚠️ LLM call failed: {e}")
        return {}

# === STEP 4: Fallback mock data ===
def mock_data():
    return {
        "DATE_LOSS": "2024-11-13",
        "INSURED_NAME": "Richard Daly",
        "MORTGAGE_CO": "Alacrity Mortgage",
        "INSURED_H_STREET": "123 Storm Ln",
        "INSURED_H_CITY": "San Antonio",
        "INSURED_H_STATE": "TX",
        "INSURED_H_ZIP": "78265",
        "DATE_INSPECTED": "2024-11-14",
        "TOL_CODE": "wind",
        "DATE_RECEIVED": "2024-11-15",
        "MORTGAGEE": "Alacrity"
    }

# === STEP 5: Fill template ===
def fill_template(docx_file, field_values):
    doc = Document(docx_file)
    for para in doc.paragraphs:
        for key, value in field_values.items():
            if f"[{key}]" in para.text:
                para.text = para.text.replace(f"[{key}]", value)
    output = BytesIO()
    doc.save(output)
    output.seek(0)
    return output

# === STREAMLIT APP ===
st.set_page_config(page_title="GLR Pipeline App", page_icon="📄")
st.title("📄 GLR Pipeline - Auto Fill Insurance Report")

template_file = st.file_uploader("Upload Template (.docx)", type=["docx"])
pdf_files = st.file_uploader("Upload Photo Reports (.pdf)", type=["pdf"], accept_multiple_files=True)

if st.button("Process"):
    if not template_file or not pdf_files:
        st.error("Please upload both the DOCX template and at least one PDF report.")
    else:
        with st.spinner("📄 Reading photo reports..."):
            text = extract_pdf_text(pdf_files)

        with st.spinner("🔍 Extracting placeholders from template..."):
            placeholders = extract_placeholders(template_file)

        with st.spinner("🤖 Calling LLM..."):
            field_values = call_llm(text, placeholders)
            if not field_values:
                st.warning("⚠️ Falling back to mock data.")
                field_values = mock_data()

        st.success("✅ Fields extracted and matched!")

        with st.spinner("📝 Filling the template..."):
            filled_doc = fill_template(template_file, field_values)

        st.download_button(
            label="📥 Download Filled Report",
            data=filled_doc,
            file_name="filled_report.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
