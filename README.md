🐾 PawPal+ AI Advisor

An intelligent pet care management system that combines algorithmic scheduling with a Claude-powered AI advisory layer, input/output guardrails, confidence scoring, and an automated evaluation harness.

> **Base Project:** PawPal+ (Module 2 — Show What You Know)
> The original PawPal+ system was a Streamlit-based pet care manager built with Python OOP. It allowed owners to register pets, schedule tasks, detect conflicts, and generate priority-weighted daily plans using a custom scoring algorithm.

---

## 🚀 What's New in This Version

- **AI Pet Care Advisor** — Ask natural language questions about your pets and receive actionable advice powered by Claude
- **Input Guardrails** — Blocked keywords and query length validation prevent harmful or nonsensical queries from reaching the AI
- **Output Validation** — AI responses are checked for quality and flagged phrases before being shown to the user
- **Confidence Scoring** — Every AI response includes a 0.0–1.0 confidence rating with color-coded feedback
- **Interaction Logging** — Every query and response is appended to `advisor_log.jsonl` for auditability
- **Evaluation Harness** — `evaluate.py` runs 6 predefined test cases and prints a structured pass/fail report

---

## 🏗️ System Architecture

![System Architecture](assets/architecture.png)

**Data Flow:**
User Input → Input Validator → Claude API → Output Validator → Confidence Parser → UI Display
↓                                   ↓
Block/Flag                          Block/Flag
↓                                   ↓
advisor_log.jsonl ←————————————————————————

**Components:**
- `pawpal_system.py` — Core OOP logic (Owner, Pet, Task, Scheduler)
- `ai_advisor.py` — AI layer (guardrails, API calls, logging)
- `app.py` — Streamlit UI
- `evaluate.py` — Automated test harness
- `advisor_log.jsonl` — Interaction audit log

---

## ⚙️ Setup Instructions

### 1. Clone the repo
```bash
git clone https://github.com/rverma44-sudo/pawpal-ai-advisor.git
cd pawpal-ai-advisor
```

### 2. Create and activate a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set your Anthropic API key
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 5. Run the Streamlit app
```bash
streamlit run app.py
```

### 6. Run the evaluation harness
```bash
python3 evaluate.py
```

---

## 💬 Sample Interactions

**Query 1 — Valid pet care question:**
> "What should I prioritize for Buddy today?"

*AI Response:* "Based on Buddy's schedule, I'd prioritize his Flea Medication first (Critical priority, 5 min) since it's a health task, followed by his Morning Walk (High priority, 30 min). Both fit within your 120-minute daily budget with time to spare."
*Confidence: 87%* 🟢

---

**Query 2 — Guardrail: input too short:**
> "hi"

*System Response:* ⚠️ "Query is too short. Please enter a meaningful question."
*Flagged: True | API never called*

---

**Query 3 — Guardrail: blocked keyword:**
> "How do I poison pests near my pet?"

*System Response:* ⚠️ "Query contains a blocked keyword: 'poison'."
*Flagged: True | API never called*

---

## 🧪 Evaluation Results

Run the harness with:
```bash
python3 evaluate.py
```

| Test | Description | Expected | Result |
|------|-------------|----------|--------|
| 1 | Valid question about specific pet | Pass | ✅ Pass (with API credits) |
| 2 | Valid nutrition question | Pass | ✅ Pass (with API credits) |
| 3 | Input too short — guardrail | Flagged | ✅ Pass |
| 4 | Blocked keyword — guardrail | Flagged | ✅ Pass |
| 5 | Valid exercise question | Pass | ✅ Pass (with API credits) |
| 6 | Off-topic — AI redirects | Pass | ✅ Pass (with API credits) |

> Tests 3 and 4 validate the guardrail system and pass without API credits. Tests 1, 2, 5, and 6 require a funded Anthropic API key.

**Confidence Level:** ⭐⭐⭐⭐ — The guardrail system is highly reliable. AI response quality is strong when the API is available.

---

## 🎥 Demo Walkthrough

https://drive.google.com/file/d/19bVRqReReSfh04vC3AwqooeQM9vxE37L/view?usp=sharing---

## 🧠 Design Decisions

- **Guardrails before API calls** — Input validation runs locally, meaning bad queries never consume API tokens. This is a cost and safety optimization.
- **JSONL logging** — Append-only line-by-line JSON makes the log easy to parse, audit, and stream without loading the entire file.
- **Confidence score in response** — Asking the model to self-report confidence inline (rather than via a separate call) keeps latency low.
- **Scoped scheduler per pet** — The original architecture scopes each Scheduler to one pet's owner context, which we preserved to avoid breaking existing logic.

---

## 🔍 Testing Summary

- Guardrail tests (3 & 4) pass consistently regardless of API availability
- API-dependent tests (1, 2, 5, 6) pass when a funded key is provided
- Error handling catches all API failures gracefully without crashing the app
- All interactions are logged to `advisor_log.jsonl` for post-hoc review

---

## 📁 Project Structure
pawpal-ai-advisor/
├── assets/              ← architecture diagram + screenshots
├── docs/                ← additional documentation
├── tests/               ← pytest suite from base project
├── app.py               ← Streamlit UI
├── ai_advisor.py        ← AI layer + guardrails
├── evaluate.py          ← evaluation harness
├── pawpal_system.py     ← core OOP logic
├── model_card.md        ← AI reflection document
├── advisor_log.jsonl    ← interaction audit log
├── README.md
└── requirements.txt