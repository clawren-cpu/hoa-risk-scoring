# HOA Risk Scoring Tool (Detailed Line-by-Line Breakdown Version)
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

def calculate_total_risk_score_detailed(
    growth, mgmt_ratio, legal_ratio,
    rc_per_unit, deductible, fidelity_ratio,
    flood_risk, tornado_risk, hail_risk
):
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

# The rest of the app would use this new scoring function
# Replace your existing calculate_total_risk_score call with this one in the full Streamlit script