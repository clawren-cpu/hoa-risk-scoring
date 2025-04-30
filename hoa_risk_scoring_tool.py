
# HOA Risk Scoring Tool (Streamlit Web App w/ ZIP + Excel Support)
import streamlit as st
import zipfile
import os
import tempfile
from PyPDF2 import PdfReader
import pandas as pd
import re

def calculate_total_risk_score(
    growth, mgmt_ratio, legal_ratio,
    rc_per_unit, deductible, fidelity_ratio,
    flood_risk="moderate", tornado_risk="moderate", hail_risk="low"
):
    score = 0
    if growth > 0.05: score += 1
    if mgmt_ratio < 0.08: score += 1
    if legal_ratio < 0.01: score += 1
    if rc_per_unit > 200000: score += 1
    if deductible <= 25000: score += 1
    if fidelity_ratio >= 0.75: score += 1
    if flood_risk in ["moderate", "high"]: score += 1
    if tornado_risk in ["moderate", "high"]: score += 1
    return score

def classify_score(score):
    if score >= 7:
        return "Low Risk"
    elif score >= 4:
        return "Medium Risk"
    else:
        return "High Risk"

def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    return "\n".join([p.extract_text() or "" for p in reader.pages])

def extract_budget_metrics(text):
    def find(pattern):
        match = re.search(pattern, text)
        return float(match.group(1).replace(",", "")) if match else 0.0

    assess_2024 = find(r"2024[^\d]*(\d{1,3}(?:,\d{3})*\.\d{2})")
    assess_2025 = find(r"2025[^\d]*(\d{1,3}(?:,\d{3})*\.\d{2})")
    mgmt_fee = find(r"Manag(?:ement)?[^\d]*(\d{1,3}(?:,\d{3})*\.\d{2})")
    legal_fee = find(r"Legal[^\d]*(\d{1,3}(?:,\d{3})*\.\d{2})")

    growth = (assess_2025 - assess_2024) / assess_2024 if assess_2024 else 0
    mgmt_ratio = mgmt_fee / assess_2025 if assess_2025 else 0
    legal_ratio = legal_fee / assess_2025 if assess_2025 else 0
    return growth, mgmt_ratio, legal_ratio, assess_2025

def extract_dec_metrics(text, units=1):
    rc_total = re.search(r"RC[^\d]*(\d{1,3}(?:,\d{3})*\.\d{2})", text)
    deductible = re.search(r"\$?(\d{1,3}(?:,\d{3})*) per unit", text)
    fidelity = re.search(r"Crime / Fidelity.*?\n.*?(\d{1,3}(?:,\d{3})*)", text)

    rc_total = float(rc_total.group(1).replace(",", "")) if rc_total else 0
    deductible = float(deductible.group(1).replace(",", "")) if deductible else 25000
    fidelity = float(fidelity.group(1).replace(",", "")) if fidelity else 0

    rc_per_unit = rc_total / units
    return rc_per_unit, deductible, fidelity

st.title("🏢 HOA Risk Scoring Tool")

uploaded_file = st.file_uploader("📂 Upload HOA ZIP or Excel Budget", type=["zip", "xlsx"])

if uploaded_file:
    with tempfile.TemporaryDirectory() as tmpdir:
        file_ext = uploaded_file.name.split(".")[-1].lower()
        fpath = os.path.join(tmpdir, uploaded_file.name)
        with open(fpath, "wb") as f:
            f.write(uploaded_file.read())

        if file_ext == "zip":
            with zipfile.ZipFile(fpath, 'r') as zip_ref:
                zip_ref.extractall(tmpdir)

            files = os.listdir(tmpdir)
            budget_pdf = next((f for f in files if "budget" in f.lower()), None)
            dec_pdf = next((f for f in files if "dec" in f.lower()), None)

            if budget_pdf and dec_pdf:
                budget_text = extract_text_from_pdf(os.path.join(tmpdir, budget_pdf))
                dec_text = extract_text_from_pdf(os.path.join(tmpdir, dec_pdf))

                growth, mgmt_ratio, legal_ratio, assessment_2025 = extract_budget_metrics(budget_text)
                rc_per_unit, deductible, fidelity = extract_dec_metrics(dec_text, units=52)
                fidelity_ratio = fidelity / assessment_2025 if assessment_2025 else 0
            else:
                st.error("❌ Could not locate required PDFs in the ZIP (Budget and Dec Page)")
                st.stop()

        elif file_ext == "xlsx":
            df = pd.read_excel(fpath)
            try:
                assess_2024 = float(df.loc[df.iloc[:,0].str.contains("2024", case=False, na=False)].iloc[0,1])
                assess_2025 = float(df.loc[df.iloc[:,0].str.contains("2025", case=False, na=False)].iloc[0,1])
                mgmt_fee = float(df.loc[df.iloc[:,0].str.contains("management", case=False, na=False)].iloc[0,1])
                legal_fee = float(df.loc[df.iloc[:,0].str.contains("legal", case=False, na=False)].iloc[0,1])
                growth = (assess_2025 - assess_2024) / assess_2024
                mgmt_ratio = mgmt_fee / assess_2025
                legal_ratio = legal_fee / assess_2025
                assessment_2025 = assess_2025
                rc_per_unit, deductible, fidelity = 248558, 25000, 200000
                fidelity_ratio = fidelity / assessment_2025
            except:
                st.error("❌ Could not extract required budget rows from Excel")
                st.stop()

        flood_risk = st.selectbox("Flood Risk", ["low", "moderate", "high"], index=1)
        tornado_risk = st.selectbox("Tornado Risk", ["low", "moderate", "high"], index=1)
        hail_risk = st.selectbox("Hail Risk", ["low", "moderate", "high"], index=0)

        score = calculate_total_risk_score(
            growth, mgmt_ratio, legal_ratio,
            rc_per_unit, deductible, fidelity_ratio,
            flood_risk, tornado_risk, hail_risk
        )
        risk_class = classify_score(score)

        st.success(f"🏷️ Total Risk Score: {score} / 8")
        st.info(f"📊 Risk Classification: **{risk_class}**")
else:
    st.markdown("Or run manually using the form below...")
    col1, col2 = st.columns(2)
    with col1:
        growth = st.number_input("Assessment Growth (%)", min_value=0.0, value=5.75) / 100
        mgmt_ratio = st.number_input("Mgmt Fee Ratio (%)", min_value=0.0, value=6.51) / 100
        legal_ratio = st.number_input("Legal Fee Ratio (%)", min_value=0.0, value=0.29) / 100
    with col2:
        rc_per_unit = st.number_input("Replacement Cost per Unit", min_value=0.0, value=248558.0)
        deductible = st.number_input("Water Deductible per Unit", min_value=0.0, value=25000.0)
        fidelity_ratio = st.number_input("Fidelity Coverage Ratio (%)", min_value=0.0, value=76.4) / 100

    flood_risk = st.selectbox("Flood Risk", ["low", "moderate", "high"], index=1, key="manual_flood")
    tornado_risk = st.selectbox("Tornado Risk", ["low", "moderate", "high"], index=1, key="manual_tornado")
    hail_risk = st.selectbox("Hail Risk", ["low", "moderate", "high"], index=0, key="manual_hail")

    if st.button("🔍 Calculate Risk Score"):
        score = calculate_total_risk_score(
            growth, mgmt_ratio, legal_ratio,
            rc_per_unit, deductible, fidelity_ratio,
            flood_risk, tornado_risk, hail_risk
        )
        risk_class = classify_score(score)

        st.success(f"🏷️ Total Risk Score: {score} / 8")
        st.info(f"📊 Risk Classification: **{risk_class}**")
