# 💊 MedAdhere — AI-Powered Medication Adherence Tracker

An AI-powered Streamlit application for tracking medication adherence, receiving smart reminders, and enabling caregivers/doctors to monitor patient trends — powered by **Gemini 2.5 Flash**.

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API Key
Edit `.env.example` and set your Gemini API key:
```
GEMINI_API_KEY=your_api_key_here
```
> Get a free API key at https://aistudio.google.com/

### 3. Run the App
```bash
streamlit run app.py
```

---

## 🔐 Demo Accounts

| Role | Username | Password |
|------|----------|----------|
| 👤 Patient | `patient1` | `pass123` |
| 👤 Patient | `patient2` | `pass123` |
| 👨‍👩‍👧 Caregiver | `caregiver1` | `pass123` |
| 🏥 Doctor | `doctor1` | `pass123` |

---

## 🌟 Features

### 👤 Patient Features
- **Log Medications** — Mark doses as Taken / Missed / Skipped for any date
- **Progress Dashboard** — Gauge chart, daily trend, per-medication breakdown, weekly heatmap
- **AI Assistant** — Multi-turn chat with Gemini 2.5 Flash for medication questions
- **Reminders** — Set per-medication time reminders with custom messages
- **Medication Manager** — Add/deactivate medications, get AI insights per drug

### 🏥 Caregiver / Doctor Features
- **Patient Overview** — Cards for each linked patient with adherence metrics
- **Detailed Analytics** — Full charts, logs table, and medication history per patient
- **AI Reports** — One-click AI-generated clinical adherence reports per patient
- **Patient Comparison** — Bar chart comparing all patients' adherence rates
- **Link Patients** — Connect to patients by username

### 🤖 AI Capabilities (Gemini 2.5 Flash)
- Context-aware medication Q&A (knows patient's current meds & adherence)
- Persistent multi-turn conversation history
- Clinical adherence report generation with trend analysis & risk assessment
- Per-medication insights (usage, side effects, tips)

---

## 📁 Project Structure

```
.
├── app.py                  # Main Streamlit entry point & auth
├── database.py             # SQLite data layer (all DB operations)
├── ai_assistant.py         # Gemini 2.5 Flash AI integration
├── patient_dashboard.py    # Patient UI (log, charts, AI chat, reminders)
├── caregiver_dashboard.py  # Caregiver/Doctor UI (analytics, AI reports)
├── charts.py               # Plotly chart components
├── requirements.txt        # Python dependencies
├── .env.example            # API key configuration
└── .streamlit/
    └── config.toml         # Streamlit theme & server settings
```

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit |
| AI | Google Gemini 2.5 Flash (`google-genai`) |
| Database | SQLite (local, zero-config) |
| Charts | Plotly |
| Data | Pandas |

---

## 📊 Adherence Scoring

| Rate | Status | Label |
|------|--------|-------|
| ≥ 80% | 🟢 Good | Target met |
| 60–79% | 🟡 Moderate | Needs attention |
| < 60% | 🔴 Low | Intervention required |
