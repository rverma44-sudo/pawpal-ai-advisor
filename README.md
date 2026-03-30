# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## Smarter Scheduling

PawPal+ includes a bunch of features that automate scheduling to make it intelligent rather than manual and laborous:

- **Sorted Schedules** — tasks are automatically sorted chronologically 
  by time so owners always see their day in order
- **Smart Filtering** — tasks can be filtered by completion status or 
  pet name to focus on what still needs to be done
- **Recurring Tasks** — daily and weekly tasks automatically reschedule 
  themselves after being marked complete, so nothing falls through 
  the cracks
- **Conflict Detection** — the scheduler warns owners when two tasks 
  are booked at the same time, for the same pet or across pets, 
  without crashing the app
- **Time-Constrained Planning** — the scheduler only includes tasks
  that fit within the owner's available daily minutes, and explains
  which tasks were excluded and why

## Testing PawPal+

The test suite uses pytest with real instantiated objects from `pawpal_system.py` so every test exercises the actual scheduling logic end to end.

### Running the tests
python -m pytest
### What is covered

- **Sorting order** — No matter what order the tasks are added, the system will automatically organize them chronologically so the schedule makes sense.
- **Handling repeating chores** — Once a daily or weekly task is completed, the app automatically creates the next occurence of it at the correct time.
- **Schedule Clashes** — If two tasks are scheduled on accident for the exact same time, the app will warn you to avoid that or allow you to address it.
- **Edge cases** — Ensures app doesn't crash with empty cariables. Empty task lists produce an empty plan without raising an exception; unknown task names return a warning string; a time budget smaller than the shortest task yields an empty plan; one-time tasks do not generate a new occurrence after completion.

**Confidence Level: 5/5 Stars. Based on my test results, I am very confident in the system's reliability.