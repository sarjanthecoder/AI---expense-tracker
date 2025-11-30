
import streamlit as st
import matplotlib.pyplot as plt
from fpdf import FPDF
import firebase_admin
from firebase_admin import credentials, auth, firestore
from datetime import datetime
import base64
import requests
import pandas as pd
import time
import json

# ------------------ CONFIG ------------------keep it as private not in oublic  this is only for demo puposes

GEMINI_API_KEY = "AIzaSyDGgu2atNoJNEl8N92mFE7JqJcApk4vb84" 

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"

# ------------------ INIT FIREBASE ------------------
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-adminsdk.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

# ------------------ FIREBASE AUTH ------------------
def sign_up_user(email, password):
    try:
        user = auth.create_user(email=email, password=password)
        return True, f"✅ User {email} created successfully."
    except Exception as e:
        return False, str(e)

def verify_login(email):
    try:
        user = auth.get_user_by_email(email)
        return True, f"✅ Logged in as {email}"
    except:
        return False, "❌ Invalid email."

# ------------------ GEMINI API ------------------
def get_gemini_advice(salary, expenses, savings):
    prompt = f"""
    I earn Rs. {salary} monthly and spend Rs. {expenses}, saving Rs. {savings}.
    Give 3 concise and practical suggestions to reduce spending or improve savings and investment options (like SIPs, mutual funds, or budget tips).
    Keep it short and simple.
    """
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload)
        if response.ok:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"❌ Gemini API Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"❌ Gemini Request Failed: {e}"

# ------------------ SESSION ------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.email = ""

# ------------------ LOGIN UI ------------------
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(to right, #232526, #414345);
        color: white;
    }
    .css-18e3th9, .css-1d391kg, .st-bq, .st-af, .st-ag, .st-ah {
        color: white !important;
    }
    .metric-label, .metric-value {
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("💸 Expense Tracker with Firebase + Gemini AI")
if not st.session_state.authenticated:
    auth_action = st.radio("Choose Action", ["Login", "Sign Up"])
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    auth_button = st.button("Submit")
    if auth_button:
        if auth_action == "Sign Up":
            success, msg = sign_up_user(email, password)
        else:
            success, msg = verify_login(email)
        st.info(msg)
        if success:
            st.session_state.authenticated = True
            st.session_state.email = email
            st.rerun()

# ------------------ LOGOUT ------------------
if st.session_state.authenticated:
    st.sidebar.success(f"Logged in as: {st.session_state.email}")
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.email = ""
        st.rerun()

# ------------------ MANUAL EXPENSE FORM ------------------
if st.session_state.authenticated:
    st.subheader("📅 Select Month")
    month = st.selectbox("Month", [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ])

    st.subheader("🧾 Enter Expenses")
    salary = st.number_input("Monthly Salary (Rs.)", min_value=0)
    rent_or_own = st.radio("Do you live in:", ["Own", "Rent"])
    rent = st.number_input("Rent (Rs.)", min_value=0) if rent_or_own == "Rent" else 0
    medical = st.number_input("Medical (Rs.)", min_value=0)
    insurance = st.number_input("Insurance (Rs.)", min_value=0)
    grocery = st.number_input("Grocery (Rs.)", min_value=0)
    personal = st.number_input("Personal Items (Rs.)", min_value=0)
    dress = st.number_input("Dress (Rs.)", min_value=0)

    if st.button("Analyze"):
        with st.spinner("🧠 Gemini is analyzing your spending patterns..."):
            total = rent + medical + insurance + grocery + personal + dress
            savings = salary - total
            advice = get_gemini_advice(salary, total, savings)

        st.metric("Total Expenses", f"Rs. {total}")
        st.metric("Savings", f"Rs. {savings}")
        st.success(advice)

        data = {
            "email": st.session_state.email,
            "month": month,
            "salary": salary,
            "rent": rent,
            "medical": medical,
            "insurance": insurance,
            "grocery": grocery,
            "personal": personal,
            "dress": dress,
            "total": total,
            "savings": savings,
            "advice": advice,
            "date": datetime.now().isoformat()
        }
        db.collection("expenses").add(data)
        st.success("✅ Expense saved to Firebase!")

        labels = ['Rent', 'Medical', 'Insurance', 'Grocery', 'Personal', 'Dress']
        values = [rent, medical, insurance, grocery, personal, dress]
        fig, ax = plt.subplots()
        ax.pie(values, labels=labels, autopct='%1.1f%%')
        ax.axis("equal")
        st.pyplot(fig)

        # Download single-month PDF (with Gemini advice)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=f"{month} Expense Report", ln=True, align='C')
        pdf.ln(10)
        for label, val in zip(labels, values):
            pdf.cell(200, 10, txt=f"{label}: Rs. {val}", ln=True)
        pdf.cell(200, 10, txt=f"Total Expenses: Rs. {total}", ln=True)
        pdf.cell(200, 10, txt=f"Savings: Rs. {savings}", ln=True)
        pdf.ln(10)
        pdf.multi_cell(0, 10, txt=f"Gemini Suggestions:\n{advice.encode('latin-1', 'ignore').decode('latin-1')}")
        pdf.output(f"{month}_Expense_Report.pdf")
        with open(f"{month}_Expense_Report.pdf", "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
            st.markdown(f'<a href="data:application/octet-stream;base64,{b64}" download="{month}_Expense_Report.pdf">📄 Download {month} Report PDF</a>', unsafe_allow_html=True)

    # ------------------ HISTORY ------------------
    st.subheader("📈 Monthly Expense History")
    docs = db.collection("expenses").where("email", "==", st.session_state.email).stream()
    history = [{"month": doc.to_dict().get("month", ""), **doc.to_dict()} for doc in docs]
    if history:
        df = pd.DataFrame(history)
        df["year"] = pd.to_datetime(df["date"]).dt.year.astype(str)

        year_filter = st.multiselect("Filter by Year", sorted(df["year"].unique()))
        if year_filter:
            df = df[df["year"].isin(year_filter)]

        st.dataframe(df[["year", "month", "salary", "total", "savings"]].sort_values(by=["year", "month"]))
        st.line_chart(df.set_index("month")[["salary", "total", "savings"]])

        if st.button("📘 Download Full-Year Expense Report"):
            yearly_pdf = FPDF()
            yearly_pdf.add_page()
            yearly_pdf.set_font("Arial", size=12)
            yearly_pdf.cell(200, 10, txt="Full-Year Expense Summary", ln=True, align='C')
            yearly_pdf.ln(10)

            for _, row in df.sort_values(by=["year", "month"]).iterrows():
                yearly_pdf.cell(200, 10, txt=f"{row['month']} {row['year']}", ln=True)
                yearly_pdf.cell(200, 10, txt=f"  Salary: Rs. {row['salary']} | Total: Rs. {row['total']} | Savings: Rs. {row['savings']}", ln=True)
                yearly_pdf.cell(200, 10, txt=f"  Rent: {row['rent']}, Medical: {row['medical']}, Insurance: {row['insurance']}, Grocery: {row['grocery']}, Personal: {row['personal']}, Dress: {row['dress']}", ln=True)
                yearly_pdf.ln(5)

            yearly_pdf.output("Yearly_Expense_Report.pdf")
            with open("Yearly_Expense_Report.pdf", "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                st.markdown(f'<a href="data:application/octet-stream;base64,{b64}" download="Yearly_Expense_Report.pdf">📘 Download Yearly Report PDF</a>', unsafe_allow_html=True)

        st.subheader("📊 Monthly Spending Pattern")
        chart_data = df.groupby("month")["total"].sum().reset_index()
        chart_data = chart_data.sort_values(by="month", key=lambda x: pd.Categorical(
            x, categories=["January","February","March","April","May","June","July","August","September","October","November","December"], ordered=True))
        st.bar_chart(chart_data.set_index("month"))
    else:
        st.info("No data found.")            

