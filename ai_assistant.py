import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
import database as db

load_dotenv(dotenv_path=".env.example")

_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set. Please add it to .env.example.")
        _client = genai.Client(api_key=api_key)
    return _client


_SYSTEM_PROMPT = """You are MedGuide AI, a compassionate and knowledgeable medication adherence assistant.
Your role is to:
1. Help patients understand their medications, potential side effects, and dosage instructions.
2. Provide motivation and encouragement to stay adherent to their medication schedule.
3. Answer general health and medication-related questions clearly and empathetically.
4. Analyse adherence patterns and provide actionable suggestions for improvement.
5. Warn patients to consult their doctor for medical advice beyond medication guidance.

Guidelines:
- Be warm, encouraging, and supportive.
- Use simple, non-technical language.
- Always recommend consulting a healthcare professional for medical decisions.
- Never diagnose conditions or prescribe medications.
- Keep responses concise and easy to read.
- Use bullet points for lists.
- If given adherence data, analyse it and provide specific insights.
"""

MODEL = "gemini-2.5-flash"


def chat_with_ai(user_id: int, user_message: str, context_data: dict = None) -> str:
    """Send a message to Gemini 2.5 Flash and return the response."""
    try:
        client = _get_client()

        # Enrich message with patient context
        enriched_message = user_message
        if context_data:
            context_parts = ["[Patient Context]"]
            if context_data.get("medications"):
                meds = context_data["medications"]
                context_parts.append(
                    "Current Medications: " + ", ".join(
                        [f"{m['name']} {m['dosage']}" for m in meds]
                    )
                )
            if context_data.get("adherence_stats"):
                s = context_data["adherence_stats"]
                context_parts.append(
                    f"Adherence Rate (30 days): {s['rate']}% "
                    f"(Taken: {s['taken']}, Missed: {s['missed']}, Skipped: {s['skipped']})"
                )
            if len(context_parts) > 1:
                enriched_message = user_message + "\n\n" + "\n".join(context_parts)

        # Build multi-turn history
        history = db.get_chat_history(user_id, limit=10)
        contents = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

        # Append current user message
        contents.append(types.Content(role="user", parts=[types.Part(text=enriched_message)]))

        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                temperature=0.7,
                max_output_tokens=1024,
            ),
        )
        reply = response.text

        # Persist conversation (store original message, not enriched)
        db.save_chat_message(user_id, "user", user_message)
        db.save_chat_message(user_id, "model", reply)

        return reply

    except Exception as e:
        error_msg = str(e)
        if "API_KEY" in error_msg.upper() or "api key" in error_msg.lower():
            return "⚠️ API key error. Please check your GEMINI_API_KEY in the .env.example file."
        return f"⚠️ AI service temporarily unavailable: {error_msg}"


def generate_adherence_report(patient_name: str, stats: dict, daily_data: list, medications: list) -> str:
    """Generate an AI-powered adherence report for doctors/caregivers."""
    try:
        client = _get_client()

        med_names = ", ".join([m["name"] for m in medications]) if medications else "None"
        daily_summary = []
        for d in daily_data[-14:]:
            rate = round(d["taken"] / d["total"] * 100) if d["total"] > 0 else 0
            daily_summary.append(f"{d['scheduled_date']}: {rate}% ({d['taken']}/{d['total']})")

        prompt = f"""Generate a comprehensive medication adherence report for the following patient data:

Patient: {patient_name}
Medications: {med_names}
Overall 30-day Adherence Rate: {stats['rate']}%
Doses Taken: {stats['taken']}
Doses Missed: {stats['missed']}
Doses Skipped: {stats['skipped']}
Total Doses: {stats['total']}

Last 14 Days Daily Adherence:
{chr(10).join(daily_summary)}

Please provide:
1. Executive Summary of adherence performance
2. Trend Analysis (improving/declining/stable)
3. Risk Assessment (high/medium/low non-adherence risk)
4. Specific recommendations for the caregiver/doctor
5. Suggested interventions if adherence is below 80%

Format the report clearly with sections and bullet points."""

        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="You are a clinical pharmacist writing a professional medication adherence report.",
                temperature=0.3,
                max_output_tokens=2048,
            ),
        )
        return response.text
    except Exception as e:
        return f"Could not generate AI report: {str(e)}"


def get_medication_insights(medication_name: str, dosage: str, instructions: str) -> str:
    """Get AI insights about a specific medication."""
    try:
        client = _get_client()
        prompt = f"""Provide a brief, patient-friendly overview of the medication:
Medication: {medication_name} ({dosage})
Instructions: {instructions}

Include:
- What it is commonly used for
- Key side effects to watch for
- Important tips for taking it correctly
- When to contact a doctor

Keep it concise and easy to understand. Always recommend consulting a doctor for personalized advice."""

        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                temperature=0.4,
                max_output_tokens=600,
            ),
        )
        return response.text
    except Exception as e:
        return f"Could not retrieve medication insights: {str(e)}"
