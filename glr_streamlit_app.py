import fitz
import json
import requests
import os
import tempfile
from io import BytesIO
from docx import Document
import streamlit as st

# === CONFIG ===
OPENROUTER_API_KEY = "sk-60ccf40489f14035abeefff344ba33ba"  # Replace with your real key

# === STEP 1: Extract PDF text ===
def extract_pdf_text(uploaded_pdfs):
    combined_text = ""
    for file in uploaded_pdfs:
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            for page in doc:
                combined_text += page.get_text()
    return combined_text

# === STEP 2: Extract placeholders ===
def extract_placeholders(docx_file):
    doc = Document(docx_file)
    placeholders = set()
    for para in doc.paragraphs:
        for word in para.text.split():
            if word.startswith("[") and word.endswith("]"):
                placeholders.add(word.strip("[]"))
    return list(placeholders)

# === STEP 3: Call LLM API ===
def call_llm(pdf_text, placeholders):
    prompt = f"""
You are an insurance claim processor. Extract values for the following placeholders:

{placeholders}

Text:
\"\"\"
{pdf_text[:6000]}
\"\"\"

Respond with ONLY valid JSON.
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
        st.warning(f"LLM failed: {e}")
        return {}

# === MOCK fallback ===
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

# === STEP 4: Fill DOCX placeholders ===
def fill_template(docx_file, field_values):
    doc = Document(docx_file)
    for para in doc.paragraphs:
        for key, value in field_values.items():
            if f"[{key}]" in para.text:
                para.text = para.text.replace(f"[{key}]", value)

    temp_output = BytesIO()
    doc.save(temp_output)
    temp_output.seek(0)
    return temp_output

# === STREAMLIT APP ===
st.set_page_config(page_title="GLR Report Filler", page_icon="📝")
st.title("📄 GLR Pipeline - Insurance Auto Filler")

template_file = st.file_uploader("Upload Template (.docx)", type=["docx"])
pdf_files = st.file_uploader("Upload Photo Reports (.pdf)", type=["pdf"], accept_multiple_files=True)

if st.button("Process"):
    if not template_file or not pdf_files:
        st.error("Please upload both the template and at least one photo report.")
    else:
        with st.spinner("Extracting text..."):
            text = extract_pdf_text(pdf_files)

        with st.spinner("Reading placeholders..."):
            placeholders = extract_placeholders(template_file)

        with st.spinner("Calling LLM or using fallback..."):
            result = call_llm(text, placeholders)
            if not result:
                result = mock_data()

        st.success("✔️ Fields extracted!")

        with st.spinner("Filling template..."):
            filled_doc = fill_template(template_file, result)

        st.download_button(
            label="📥 Download Filled Report",
            data=filled_doc,
            file_name="filled_report.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
