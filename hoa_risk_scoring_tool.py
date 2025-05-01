import streamlit as st
import zipfile
import os
import tempfile
from PyPDF2 import PdfReader
import pandas as pd
import re
from io import StringIO, BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def get_metric_row(label, actual, threshold, passed):
    return {
        "Metric": label,
        "Actual Value": actual,
        "Threshold": threshold,
        "Pass?": "✅" if passed else "❌"
    }

def calculate_total_risk_score_detailed(growth, mgmt_ratio, legal_ratio, rc_per_unit, deductible, fidelity_ratio, flood_risk, tornado_risk, hail_risk):
    rows = []
    score = 0
    def test(condition, label, actual, threshold):
        nonlocal score
        passed = condition
        if passed: score += 1
        rows.append(get_metric_row(label, actual, threshold, passed))
    test(growth > 0.05, "Assessment Growth", f"{growth:.2%}", "> 5%")
    test(mgmt_ratio < 0.08, "Mgmt Fee Ratio", f"{mgmt_ratio:.2%}", "< 8%")
    test(legal_ratio < 0.01, "Legal Fee Ratio", f"{legal_ratio:.2%}", "< 1%")
    test(rc_per_unit > 200000, "Replacement Cost / Unit", f"${rc_per_unit:,.0f}", "> $200,000")
    test(deductible <= 25000, "Water Deductible / Unit", f"${deductible:,.0f}", "≤ $25,000")
    test(fidelity_ratio >= 0.75, "Fidelity Coverage Ratio", f"{fidelity_ratio:.2%}", "≥ 75%")
    test(flood_risk in ["moderate", "high"], "Flood Risk", flood_risk, "moderate or high")
    test(tornado_risk in ["moderate", "high"], "Tornado Risk", tornado_risk, "moderate or high")
    return score, pd.DataFrame(rows)

def classify_score(score):
    return "Low Risk" if score >= 7 else "Medium Risk" if score >= 4 else "High Risk"

def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    return "\n".join([p.extract_text() or "" for p in reader.pages])

def extract_budget_metrics(text):
    def find(pattern): return float(re.search(pattern, text).group(1).replace(",", "")) if re.search(pattern, text) else 0.0
    assess_2024 = find(r"2024[^\d]*(\d{1,3}(?:,\d{3})*\.\d{2})")
    assess_2025 = find(r"2025[^\d]*(\d{1,3}(?:,\d{3})*\.\d{2})")
    mgmt_fee = find(r"Manag(?:ement)?[^\d]*(\d{1,3}(?:,\d{3})*\.\d{2})")
    legal_fee = find(r"Legal[^\d]*(\d{1,3}(?:,\d{3})*\.\d{2})")
    growth = (assess_2025 - assess_2024) / assess_2024 if assess_2024 else 0
    mgmt_ratio = mgmt_fee / assess_2025 if assess_2025 else 0
    legal_ratio = legal_fee / assess_2025 if assess_2025 else 0
    return growth, mgmt_ratio, legal_ratio, assess_2025

def extract_dec_metrics(text, units=1):
    rc_total = float(re.search(r"RC[^\d]*(\d{1,3}(?:,\d{3})*\.\d{2})", text).group(1).replace(",", "")) if re.search(r"RC", text) else 0
    deductible = float(re.search(r"\$?(\d{1,3}(?:,\d{3})*) per unit", text).group(1).replace(",", "")) if re.search(r"per unit", text) else 25000
    fidelity = float(re.search(r"Crime / Fidelity.*?\n.*?(\d{1,3}(?:,\d{3})*)", text).group(1).replace(",", "")) if re.search(r"Fidelity", text) else 0
    return rc_total / units, deductible, fidelity

def generate_pdf(score, risk_class, breakdown, filename="hoa_risk_report.pdf"):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "HOA Risk Scoring Report")
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 80, f"Association File: {filename}")
    c.drawString(50, height - 100, f"Total Risk Score: {score} / 8")
    c.drawString(50, height - 120, f"Risk Classification: {risk_class}")
    c.drawString(50, height - 160, "Breakdown:")
    y = height - 180
    for row in breakdown:
        c.drawString(60, y, f"{row['Pass?']} {row['Metric']} (Actual: {row['Actual Value']}, Threshold: {row['Threshold']})")
        y -= 20
    c.save()
    buffer.seek(0)
    return buffer

# Streamlit UI
st.title("🏢 HOA Risk Scoring Tool")
uploaded_file = st.file_uploader("📂 Upload HOA ZIP or Excel Budget", type=["zip", "xlsx"])

if uploaded_file:
    filename = uploaded_file.name
    with tempfile.TemporaryDirectory() as tmpdir:
        ext = filename.split(".")[-1].lower()
        fpath = os.path.join(tmpdir, filename)
        with open(fpath, "wb") as f: f.write(uploaded_file.read())

        if ext == "zip":
            with zipfile.ZipFile(fpath, "r") as zip_ref: zip_ref.extractall(tmpdir)
            files = os.listdir(tmpdir)
            budget = next((f for f in files if "budget" in f.lower()), None)
            dec = next((f for f in files if "dec" in f.lower()), None)
            if not (budget and dec): st.error("❌ Missing budget or dec page PDF."); st.stop()
            btxt, dtxt = extract_text_from_pdf(os.path.join(tmpdir, budget)), extract_text_from_pdf(os.path.join(tmpdir, dec))
            g, m, l, a = extract_budget_metrics(btxt)
            rc, d, f = extract_dec_metrics(dtxt, units=52)
            fr = f / a if a else 0
        elif ext == "xlsx":
            df = pd.read_excel(fpath)
            assess_2024 = float(df.loc[df.iloc[:,0].str.contains("2024", case=False)].iloc[0,1])
            assess_2025 = float(df.loc[df.iloc[:,0].str.contains("2025", case=False)].iloc[0,1])
            mgmt = float(df.loc[df.iloc[:,0].str.contains("management", case=False)].iloc[0,1])
            legal = float(df.loc[df.iloc[:,0].str.contains("legal", case=False)].iloc[0,1])
            g, m, l, a, rc, d, f = (assess_2025 - assess_2024)/assess_2024, mgmt/assess_2025, legal/assess_2025, assess_2025, 248558, 25000, 200000
            fr = f / a
        else: st.error("❌ Invalid file format"); st.stop()

        flood = st.selectbox("Flood Risk", ["low", "moderate", "high"], index=1)
        tornado = st.selectbox("Tornado Risk", ["low", "moderate", "high"], index=1)
        hail = st.selectbox("Hail Risk", ["low", "moderate", "high"], index=0)
        score, table = calculate_total_risk_score_detailed(g, m, l, rc, d, fr, flood, tornado, hail)
        rclass = classify_score(score)
        st.success(f"✅ Total Risk Score: {score} / 8")
        st.info(f"📊 Risk Classification: **{rclass}**")
        st.dataframe(table, use_container_width=True)

        csv = StringIO(); table.to_csv(csv, index=False)
        st.download_button("📥 Download CSV", csv.getvalue(), "hoa_risk_breakdown.csv", "text/csv")
        pdf = generate_pdf(score, rclass, table.to_dict("records"), filename)
        st.download_button("📄 Download PDF", pdf, "hoa_risk_report.pdf", "application/pdf")
else:
    st.warning("📂 Upload a file to begin.")