import streamlit as st
from datetime import date, datetime, timedelta
import database as db
import ai_assistant as ai
import charts


def render_patient_dashboard(user: dict):
    st.title(f"💊 My Medications — {user['full_name']}")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📋 Log Today's Doses", "📊 My Progress", "💬 AI Assistant", "⏰ Reminders", "💉 My Medications"]
    )

    with tab1:
        _log_doses_tab(user)

    with tab2:
        _progress_tab(user)

    with tab3:
        _ai_chat_tab(user)

    with tab4:
        _reminders_tab(user)

    with tab5:
        _medications_tab(user)


# ── Tab: Log Doses ────────────────────────────────────────────────────────────

def _log_doses_tab(user: dict):
    st.subheader("📋 Log Today's Medication Doses")

    today = date.today()
    log_date = st.date_input("Select Date", value=today, max_value=today)
    log_date_str = log_date.isoformat()

    medications = db.get_medications(user["id"])

    if not medications:
        st.warning("You have no active medications. Ask your doctor or add medications in the 'My Medications' tab.")
        return

    st.markdown("---")

    for med in medications:
        with st.expander(f"💊 **{med['name']}** — {med['dosage']}  |  {med['frequency']}", expanded=True):
            if med.get("instructions"):
                st.caption(f"📝 {med['instructions']}")

            for dose_num in range(1, med["times_per_day"] + 1):
                # Fetch current log
                conn = db.get_connection()
                existing = conn.execute(
                    "SELECT * FROM medication_logs WHERE medication_id=? AND scheduled_date=? AND dose_number=?",
                    (med["id"], log_date_str, dose_num),
                ).fetchone()
                conn.close()

                existing = dict(existing) if existing else None
                current_status = existing["status"] if existing else None

                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                label = f"Dose {dose_num}" if med["times_per_day"] > 1 else "Dose"

                with col1:
                    status_icon = {"taken": "✅", "missed": "❌", "skipped": "⏭️"}.get(current_status, "⬜")
                    st.markdown(f"**{status_icon} {label}**")

                notes_key = f"notes_{med['id']}_{dose_num}_{log_date_str}"
                notes = st.text_input("Notes (optional)", key=notes_key, label_visibility="collapsed",
                                      placeholder="Optional note...")

                btn_col1, btn_col2, btn_col3 = st.columns(3)
                with btn_col1:
                    if st.button("✅ Taken", key=f"taken_{med['id']}_{dose_num}_{log_date_str}",
                                 use_container_width=True,
                                 type="primary" if current_status == "taken" else "secondary"):
                        db.log_medication(med["id"], user["id"], log_date_str, "taken", dose_num, notes)
                        st.success("Logged as Taken!")
                        st.rerun()

                with btn_col2:
                    if st.button("❌ Missed", key=f"missed_{med['id']}_{dose_num}_{log_date_str}",
                                 use_container_width=True):
                        db.log_medication(med["id"], user["id"], log_date_str, "missed", dose_num, notes)
                        st.warning("Logged as Missed.")
                        st.rerun()

                with btn_col3:
                    if st.button("⏭️ Skipped", key=f"skipped_{med['id']}_{dose_num}_{log_date_str}",
                                 use_container_width=True):
                        db.log_medication(med["id"], user["id"], log_date_str, "skipped", dose_num, notes)
                        st.info("Logged as Skipped.")
                        st.rerun()

    # Quick stats for selected date
    st.markdown("---")
    logs_today = [
        l for l in db.get_logs(user["id"], days=1)
        if l["scheduled_date"] == log_date_str
    ]
    if logs_today:
        taken = sum(1 for l in logs_today if l["status"] == "taken")
        total = len(logs_today)
        pct = round(taken / total * 100)
        color = "#2ecc71" if pct >= 80 else "#f39c12" if pct >= 60 else "#e74c3c"
        charts.metric_card(
            f"Today's Adherence ({log_date_str})",
            f"{taken}/{total} doses",
            f"{pct}% adherence",
            color,
        )


# ── Tab: Progress ─────────────────────────────────────────────────────────────

def _progress_tab(user: dict):
    st.subheader("📊 My Adherence Progress")

    days = st.select_slider("Time Range", options=[7, 14, 30, 60, 90], value=30)

    stats = db.get_adherence_stats(user["id"], days)
    daily_data = db.get_daily_adherence(user["id"], days)
    logs = db.get_logs(user["id"], days)

    # Top metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        color = "#2ecc71" if stats["rate"] >= 80 else "#f39c12" if stats["rate"] >= 60 else "#e74c3c"
        charts.metric_card("Adherence Rate", f"{stats['rate']}%", f"Last {days} days", color)
    with col2:
        charts.metric_card("✅ Taken", str(stats["taken"]), "doses", "#2ecc71")
    with col3:
        charts.metric_card("❌ Missed", str(stats["missed"]), "doses", "#e74c3c")
    with col4:
        charts.metric_card("⏭️ Skipped", str(stats["skipped"]), "doses", "#f39c12")

    # Adherence gauge
    col_gauge, col_donut = st.columns(2)
    with col_gauge:
        charts.render_adherence_gauge(stats["rate"])
    with col_donut:
        charts.render_status_donut(stats)

    # Daily trend
    charts.render_daily_trend(daily_data, f"{days}-Day Adherence Trend")

    # Per-medication breakdown
    charts.render_medication_breakdown(logs)

    # Heatmap
    charts.render_weekly_heatmap(user["id"])

    # Adherence badge
    st.markdown("---")
    if stats["rate"] >= 90:
        st.success("🏆 **Excellent adherence!** Keep up the great work!")
    elif stats["rate"] >= 80:
        st.success("✅ **Good adherence!** You're meeting the 80% target.")
    elif stats["rate"] >= 60:
        st.warning("⚠️ **Moderate adherence.** Try to take your medications more consistently.")
    else:
        st.error("🚨 **Low adherence detected.** Please speak with your doctor or caregiver.")


# ── Tab: AI Chat ──────────────────────────────────────────────────────────────

def _ai_chat_tab(user: dict):
    st.subheader("💬 MedGuide AI Assistant")
    st.caption("Ask me anything about your medications, adherence tips, or health questions!")

    # Load history
    if "chat_messages" not in st.session_state:
        history = db.get_chat_history(user["id"], limit=20)
        st.session_state.chat_messages = history if history else []

    # Display chat
    for msg in st.session_state.chat_messages:
        avatar = "🧑" if msg["role"] == "user" else "🤖"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # Suggested prompts
    if not st.session_state.chat_messages:
        st.markdown("**💡 Try asking:**")
        suggestions = [
            "What are common side effects of Metformin?",
            "Why is it important to take blood pressure medications consistently?",
            "What should I do if I miss a dose?",
            "How can I improve my medication adherence?",
        ]
        cols = st.columns(2)
        for i, suggestion in enumerate(suggestions):
            with cols[i % 2]:
                if st.button(suggestion, key=f"suggest_{i}", use_container_width=True):
                    st.session_state.suggested_prompt = suggestion
                    st.rerun()

    # Handle suggested prompt
    if "suggested_prompt" in st.session_state:
        prompt = st.session_state.pop("suggested_prompt")
        _process_ai_message(user, prompt)
        st.rerun()

    # Chat input
    if prompt := st.chat_input("Ask MedGuide AI..."):
        _process_ai_message(user, prompt)
        st.rerun()


def _process_ai_message(user: dict, prompt: str):
    st.session_state.chat_messages.append({"role": "user", "content": prompt})

    # Build context
    medications = db.get_medications(user["id"])
    stats = db.get_adherence_stats(user["id"])
    context = {"medications": medications, "adherence_stats": stats}

    response = ai.chat_with_ai(user["id"], prompt, context)
    st.session_state.chat_messages.append({"role": "model", "content": response})


# ── Tab: Reminders ────────────────────────────────────────────────────────────

def _reminders_tab(user: dict):
    st.subheader("⏰ Medication Reminders")

    medications = db.get_medications(user["id"])
    reminders = db.get_reminders(user["id"])

    # Today's reminder notifications
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    due_reminders = [r for r in reminders if r["reminder_time"] <= current_time]

    if due_reminders:
        st.warning(f"🔔 **{len(due_reminders)} reminder(s) due today!**")
        for r in due_reminders:
            st.info(f"⏰ **{r['reminder_time']}** — {r['med_name']} | {r.get('message', 'Time to take your medication!')}")

    # Add reminder
    st.markdown("### ➕ Add New Reminder")
    if medications:
        with st.form("add_reminder_form"):
            col1, col2 = st.columns(2)
            with col1:
                med_options = {m["name"]: m["id"] for m in medications}
                selected_med = st.selectbox("Medication", list(med_options.keys()))
            with col2:
                reminder_time = st.time_input("Reminder Time", value=datetime.strptime("08:00", "%H:%M").time())

            message = st.text_input("Custom Message (optional)", placeholder="Time to take your medication!")

            if st.form_submit_button("➕ Add Reminder", use_container_width=True, type="primary"):
                db.add_reminder(
                    user["id"],
                    med_options[selected_med],
                    reminder_time.strftime("%H:%M"),
                    message or f"Time to take {selected_med}!",
                )
                st.success("Reminder added!")
                st.rerun()
    else:
        st.info("Add medications first before setting reminders.")

    # Active reminders list
    st.markdown("### 📋 Active Reminders")
    if reminders:
        for r in reminders:
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.markdown(f"**{r['med_name']}**")
            with col2:
                st.markdown(f"⏰ {r['reminder_time']}")
            with col3:
                if st.button("🗑️", key=f"del_rem_{r['id']}", help="Delete reminder"):
                    db.delete_reminder(r["id"])
                    st.rerun()
    else:
        st.info("No active reminders set.")


# ── Tab: Medications Management ───────────────────────────────────────────────

def _medications_tab(user: dict):
    st.subheader("💉 My Medications")

    medications = db.get_medications(user["id"])

    # Add new medication
    with st.expander("➕ Add New Medication", expanded=False):
        with st.form("add_med_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Medication Name *", placeholder="e.g., Metformin")
                dosage = st.text_input("Dosage *", placeholder="e.g., 500mg")
                frequency = st.selectbox("Frequency", ["Once daily", "Twice daily", "Three times daily",
                                                        "Four times daily", "Every other day", "Weekly", "As needed"])
            with col2:
                times_per_day = st.number_input("Doses per Day", min_value=1, max_value=6, value=1)
                start_date = st.date_input("Start Date", value=date.today())
                end_date = st.date_input("End Date (optional)", value=None)
                prescribed_by = st.text_input("Prescribed by", placeholder="Doctor's name")

            instructions = st.text_area("Instructions", placeholder="e.g., Take with food")

            if st.form_submit_button("💊 Add Medication", use_container_width=True, type="primary"):
                if name and dosage:
                    db.add_medication(
                        user["id"], name, dosage, frequency, times_per_day,
                        instructions, start_date.isoformat(),
                        end_date.isoformat() if end_date else None,
                        prescribed_by,
                    )
                    st.success(f"✅ {name} added!")
                    st.rerun()
                else:
                    st.error("Please fill in medication name and dosage.")

    # Current medications list
    if medications:
        for med in medications:
            with st.expander(f"💊 **{med['name']}** — {med['dosage']} | {med['frequency']}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**Instructions:** {med.get('instructions', 'N/A')}")
                    st.markdown(f"**Prescribed by:** {med.get('prescribed_by', 'N/A')}")
                    st.markdown(f"**Start Date:** {med['start_date']}")
                    if med.get("end_date"):
                        st.markdown(f"**End Date:** {med['end_date']}")
                    st.markdown(f"**Doses per day:** {med['times_per_day']}")

                with col2:
                    # AI Insights button
                    if st.button("🤖 AI Insights", key=f"insights_{med['id']}", use_container_width=True):
                        with st.spinner("Getting AI insights..."):
                            insight = ai.get_medication_insights(
                                med["name"], med["dosage"], med.get("instructions", "")
                            )
                        st.info(insight)

                    if st.button("🗑️ Deactivate", key=f"deact_{med['id']}", use_container_width=True):
                        db.deactivate_medication(med["id"])
                        st.warning(f"{med['name']} deactivated.")
                        st.rerun()
    else:
        st.info("No medications added yet.")
