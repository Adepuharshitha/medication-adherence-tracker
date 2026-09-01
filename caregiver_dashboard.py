import streamlit as st
from datetime import date, datetime, timedelta
import database as db
import ai_assistant as ai
import charts


def render_caregiver_dashboard(user: dict):
    role_label = "Doctor" if user["role"] == "doctor" else "Caregiver"
    st.title(f"🏥 {role_label} Dashboard — {user['full_name']}")

    tab1, tab2, tab3 = st.tabs(["👥 Patient Overview", "📈 Detailed Analytics", "🤖 AI Reports"])

    with tab1:
        _patient_overview_tab(user)

    with tab2:
        _detailed_analytics_tab(user)

    with tab3:
        _ai_reports_tab(user)


# ── Tab: Patient Overview ─────────────────────────────────────────────────────

def _patient_overview_tab(user: dict):
    st.subheader("👥 My Patients")

    patients = db.get_patients_for_caregiver(user["id"])

    # Link new patient
    with st.expander("🔗 Link New Patient"):
        with st.form("link_patient_form"):
            patient_username = st.text_input("Patient Username", placeholder="Enter patient's username")
            if st.form_submit_button("Link Patient", use_container_width=True, type="primary"):
                if patient_username:
                    success, msg = db.link_patient(user["id"], patient_username)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    if not patients:
        st.info("No patients linked yet. Use the form above to link a patient.")
        return

    # Patient cards grid
    st.markdown("---")
    for i in range(0, len(patients), 2):
        cols = st.columns(2)
        for j, patient in enumerate(patients[i:i + 2]):
            with cols[j]:
                _render_patient_card(patient)


def _render_patient_card(patient: dict):
    stats = db.get_adherence_stats(patient["id"], days=30)
    meds = db.get_medications(patient["id"])
    rate = stats["rate"]

    color = "#2ecc71" if rate >= 80 else "#f39c12" if rate >= 60 else "#e74c3c"
    status_icon = "🟢" if rate >= 80 else "🟡" if rate >= 60 else "🔴"
    status_text = "Good" if rate >= 80 else "Moderate" if rate >= 60 else "Needs Attention"

    with st.container(border=True):
        st.markdown(f"### 👤 {patient['full_name']}")
        st.caption(f"@{patient['username']} · {patient.get('email', '')}")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Adherence Rate", f"{rate}%", delta=f"{rate - 80:.1f}% vs target")
        with col2:
            st.metric("Active Medications", len(meds))

        st.markdown(f"{status_icon} **Status:** {status_text}")

        prog_val = rate / 100
        st.progress(prog_val, text=f"{rate}% adherence")

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("✅ Taken", stats["taken"])
        with col_b:
            st.metric("❌ Missed", stats["missed"])
        with col_c:
            st.metric("⏭️ Skipped", stats["skipped"])

        if st.button(f"📊 Full Report", key=f"report_{patient['id']}", use_container_width=True):
            st.session_state["selected_patient_id"] = patient["id"]
            st.session_state["selected_patient_name"] = patient["full_name"]
            st.rerun()


# ── Tab: Detailed Analytics ───────────────────────────────────────────────────

def _detailed_analytics_tab(user: dict):
    st.subheader("📈 Detailed Patient Analytics")

    patients = db.get_patients_for_caregiver(user["id"])
    if not patients:
        st.info("No patients linked.")
        return

    patient_map = {p["full_name"]: p for p in patients}
    default_patient = st.session_state.get("selected_patient_name", list(patient_map.keys())[0])

    selected_name = st.selectbox(
        "Select Patient",
        list(patient_map.keys()),
        index=list(patient_map.keys()).index(default_patient) if default_patient in patient_map else 0,
    )
    patient = patient_map[selected_name]

    days = st.select_slider("Time Range", options=[7, 14, 30, 60, 90], value=30)

    stats = db.get_adherence_stats(patient["id"], days)
    daily_data = db.get_daily_adherence(patient["id"], days)
    logs = db.get_logs(patient["id"], days)
    medications = db.get_medications(patient["id"])

    # Header metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        color = "#2ecc71" if stats["rate"] >= 80 else "#f39c12" if stats["rate"] >= 60 else "#e74c3c"
        charts.metric_card("Adherence Rate", f"{stats['rate']}%", f"Last {days} days", color)
    with col2:
        charts.metric_card("✅ Taken", str(stats["taken"]), "doses", "#2ecc71")
    with col3:
        charts.metric_card("❌ Missed", str(stats["missed"]), "doses", "#e74c3c")
    with col4:
        charts.metric_card("Active Meds", str(len(medications)), "medications", "#3b82d4")

    # Charts
    col_g, col_d = st.columns(2)
    with col_g:
        charts.render_adherence_gauge(stats["rate"])
    with col_d:
        charts.render_status_donut(stats)

    charts.render_daily_trend(daily_data, f"{selected_name} — {days}-Day Adherence Trend")
    charts.render_medication_breakdown(logs)
    charts.render_weekly_heatmap(patient["id"])

    # Medication details table
    st.markdown("### 💊 Medication Details")
    if medications:
        import pandas as pd
        med_df = pd.DataFrame(medications)[["name", "dosage", "frequency", "times_per_day", "start_date", "prescribed_by", "instructions"]]
        med_df.columns = ["Name", "Dosage", "Frequency", "Doses/Day", "Start Date", "Prescribed By", "Instructions"]
        st.dataframe(med_df, use_container_width=True, hide_index=True)

    # Recent logs table
    st.markdown("### 📋 Recent Dose Logs")
    if logs:
        import pandas as pd
        log_df = pd.DataFrame(logs[:50])[["scheduled_date", "med_name", "dosage", "dose_number", "status", "taken_at", "notes"]]
        log_df.columns = ["Date", "Medication", "Dosage", "Dose #", "Status", "Taken At", "Notes"]
        log_df["Status"] = log_df["Status"].map({"taken": "✅ Taken", "missed": "❌ Missed", "skipped": "⏭️ Skipped"})

        def row_color(row):
            if "Taken" in str(row["Status"]):
                return ["background-color: #e8f5e9"] * len(row)
            elif "Missed" in str(row["Status"]):
                return ["background-color: #fdecea"] * len(row)
            else:
                return ["background-color: #fff3e0"] * len(row)

        styled = log_df.style.apply(row_color, axis=1)
        st.dataframe(styled, use_container_width=True, hide_index=True)


# ── Tab: AI Reports ───────────────────────────────────────────────────────────

def _ai_reports_tab(user: dict):
    st.subheader("🤖 AI-Powered Adherence Reports")
    st.caption("Generate intelligent adherence reports and recommendations using Gemini AI.")

    patients = db.get_patients_for_caregiver(user["id"])
    if not patients:
        st.info("No patients linked.")
        return

    patient_map = {p["full_name"]: p for p in patients}
    selected_name = st.selectbox("Select Patient for Report", list(patient_map.keys()), key="ai_report_patient")
    patient = patient_map[selected_name]

    col1, col2 = st.columns(2)
    with col1:
        report_days = st.selectbox("Analysis Period", [7, 14, 30, 60, 90], index=2, format_func=lambda x: f"{x} days")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        generate_btn = st.button("🤖 Generate AI Report", use_container_width=True, type="primary")

    if generate_btn:
        stats = db.get_adherence_stats(patient["id"], report_days)
        daily_data = db.get_daily_adherence(patient["id"], report_days)
        medications = db.get_medications(patient["id"])

        with st.spinner("🤖 Generating AI analysis..."):
            report = ai.generate_adherence_report(
                patient["full_name"], stats, daily_data, medications
            )

        st.markdown("---")
        st.markdown(f"### 📄 Adherence Report: {patient['full_name']}")
        st.caption(f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')} | {report_days}-day analysis")
        st.markdown(report)

        # Quick stats summary
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            color = "#2ecc71" if stats["rate"] >= 80 else "#f39c12" if stats["rate"] >= 60 else "#e74c3c"
            charts.metric_card("Overall Adherence", f"{stats['rate']}%", f"{report_days} days", color)
        with col2:
            charts.metric_card("Total Doses", str(stats["total"]), "scheduled", "#3b82d4")
        with col3:
            missed_pct = round(stats["missed"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0
            charts.metric_card("Missed Rate", f"{missed_pct}%", "of all doses", "#e74c3c")

    # Comparison chart for all patients
    st.markdown("---")
    st.markdown("### 📊 All Patients Adherence Comparison")
    if patients:
        import plotly.graph_objects as go

        patient_names = []
        patient_rates = []
        patient_colors = []

        for p in patients:
            s = db.get_adherence_stats(p["id"], 30)
            patient_names.append(p["full_name"])
            patient_rates.append(s["rate"])
            patient_colors.append("#2ecc71" if s["rate"] >= 80 else "#f39c12" if s["rate"] >= 60 else "#e74c3c")

        fig = go.Figure(
            go.Bar(
                x=patient_names,
                y=patient_rates,
                marker_color=patient_colors,
                text=[f"{r}%" for r in patient_rates],
                textposition="outside",
            )
        )
        fig.add_hline(y=80, line_dash="dash", line_color="#e74c3c", annotation_text="80% Target")
        fig.update_layout(
            title="30-Day Adherence Comparison (All Patients)",
            yaxis=dict(range=[0, 115], title="Adherence (%)"),
            xaxis_title="Patient",
            height=350,
            margin=dict(l=20, r=20, t=50, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)
