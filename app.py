import streamlit as st
from pawpal_system import Owner, Pet, Task, Scheduler
from ai_advisor import get_ai_advice, log_interaction

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

# Owner must persist so pets and available-time settings survive every rerun
if "owner" not in st.session_state:
    st.session_state["owner"] = Owner.load_from_json()

# The active pet must persist so task additions target the correct Pet across reruns
if "current_pet" not in st.session_state:
    st.session_state["current_pet"] = None

# The scheduler must persist so the last generated plan is still visible after any widget interaction
if "scheduler" not in st.session_state:
    st.session_state["scheduler"] = None

# Convenience alias — updated at the top of every rerun
owner: Owner = st.session_state["owner"]


def _make_scoped_scheduler(owner: Owner, pet: Pet) -> Scheduler:
    """Build a Scheduler scoped to one pet, sharing the owner's time budget."""
    scoped = Owner(owner.name, owner.email, owner.available_minutes_per_day)
    scoped.add_pet(pet)
    return Scheduler(scoped)


def _toggle_task(task_name: str, cb_key: str) -> None:
    """Toggle task completion state, save, and regenerate the schedule."""
    new_value = st.session_state[cb_key]
    sched: Scheduler | None = st.session_state["scheduler"]
    own: Owner = st.session_state["owner"]
    if sched is None:
        return
    target = next((t for t in sched.scheduled_tasks if t.name == task_name), None)
    if target is None:
        return
    if new_value:
        sched.mark_task_complete(task_name)
    else:
        target.reset()
    own.save_to_json()
    sched.generate_plan()


# --- Sidebar: Daily Summary ------------------------------------------------
with st.sidebar:
    st.header("📊 Daily Summary")
    st.markdown(f"**Owner:** {owner.name}")
    st.markdown(f"**Daily budget:** {owner.available_minutes_per_day} min")

    all_pets = owner.get_pets()
    all_tasks = owner.get_all_tasks()
    st.markdown(f"**Pets registered:** {len(all_pets)}")
    st.markdown(f"**Total tasks:** {len(all_tasks)}")

    sched_sidebar: Scheduler | None = st.session_state["scheduler"]
    if sched_sidebar and sched_sidebar.scheduled_tasks:
        scheduled_today = sched_sidebar.scheduled_tasks
        completed_count = sum(1 for t in scheduled_today if t.is_completed)
        pending_count = len(scheduled_today) - completed_count
        st.markdown(f"**Completed today:** {completed_count}")
        st.markdown(f"**Pending today:** {pending_count}")
        pct = completed_count / len(scheduled_today) if scheduled_today else 0.0
        st.progress(pct, text=f"{completed_count}/{len(scheduled_today)} tasks done")
    else:
        st.info("No schedule generated yet.")


# ---------------------------------------------------------------------------
st.title("🐾 PawPal+")

# --- Owner settings --------------------------------------------------------
st.subheader("Owner Settings")
with st.form("owner_form"):
    col1, col2 = st.columns(2)
    with col1:
        owner_name_input = st.text_input("Your name", value=owner.name)
    with col2:
        available_input = st.number_input(
            "Available minutes per day",
            min_value=1,
            max_value=1440,
            value=owner.available_minutes_per_day,
        )
    if st.form_submit_button("Update owner"):
        if not owner_name_input.strip():
            st.error("Owner name cannot be empty.")
        else:
            owner.name = owner_name_input.strip()
            owner.set_available_time(int(available_input))
            owner.save_to_json()
            st.success(f"Updated: {owner.name}, {owner.available_minutes_per_day} min/day.")

st.divider()

# --- Add a pet -------------------------------------------------------------
st.subheader("Add a Pet")
with st.form("add_pet_form"):
    col1, col2 = st.columns(2)
    with col1:
        pet_name_input = st.text_input("Pet name")
        species_input = st.selectbox("Species", ["Dog", "Cat", "Bird", "Rabbit", "Other"])
    with col2:
        breed_input = st.text_input("Breed")
        age_input = st.number_input("Age (years)", min_value=0, max_value=30, value=1)
    health_input = st.text_input("Health notes (comma-separated, optional)")
    if st.form_submit_button("Add pet"):
        if not pet_name_input.strip():
            st.error("Pet name cannot be empty.")
        elif not breed_input.strip():
            st.error("Breed cannot be empty.")
        else:
            health_notes = [n.strip() for n in health_input.split(",") if n.strip()]
            new_pet = Pet(
                name=pet_name_input.strip(),
                species=species_input,
                breed=breed_input.strip(),
                age_years=int(age_input),
                health_notes=health_notes,
            )
            owner.add_pet(new_pet)
            owner.save_to_json()
            st.success(f"{new_pet.name} ({new_pet.species}) added successfully.")

pets = owner.get_pets()
if pets:
    st.markdown("**Your pets:**")
    for pet in pets:
        with st.expander(f"🐾 {pet.name} — {pet.species} ({pet.breed}, {pet.age_years} yrs)"):
            st.markdown(
                f"**Species:** {pet.species}  |  **Breed:** {pet.breed}  |  **Age:** {pet.age_years} yrs"
            )
            if pet.health_notes:
                st.markdown(f"**Health notes:** {', '.join(pet.health_notes)}")

            pet_tasks = pet.get_tasks()
            if pet_tasks:
                total_task_min = pet.get_total_task_duration()
                budget = owner.available_minutes_per_day
                st.markdown(f"**Task duration total:** {total_task_min} / {budget} min")
                st.table(
                    [
                        {
                            "Task": t.display_name,
                            "Priority": t.priority_label,
                            "Duration (min)": t.duration_minutes,
                            "Category": t.category,
                        }
                        for t in pet_tasks
                    ]
                )
            else:
                st.info("No tasks added for this pet yet.")

st.divider()

# --- Add a task ------------------------------------------------------------
st.subheader("Schedule a Task")

if not pets:
    st.info("Add at least one pet above before scheduling tasks.")
else:
    selected_name = st.selectbox("Select pet", [p.name for p in pets])
    selected_pet: Pet = next(p for p in pets if p.name == selected_name)
    st.session_state["current_pet"] = selected_pet

    with st.form("add_task_form"):
        col1, col2 = st.columns(2)
        with col1:
            task_name_input = st.text_input("Task name")
            duration_input = st.number_input(
                "Duration (minutes)", min_value=1, max_value=480, value=20
            )
        with col2:
            _PRIORITY_OPTIONS = [
                "1 — Minimal ⚪",
                "2 — Low 🟢",
                "3 — Medium 🟡",
                "4 — High 🟠",
                "5 — Critical 🔴",
            ]
            _priority_label = st.selectbox("Priority", _PRIORITY_OPTIONS, index=2)
            priority_input = int(_priority_label[0])
            category_input = st.selectbox(
                "Category",
                ["exercise", "nutrition", "health", "hygiene", "enrichment", "grooming", "other"],
            )
        if st.form_submit_button("Add task & generate plan"):
            if not task_name_input.strip():
                st.error("Task name cannot be empty.")
            else:
                new_task = Task(
                    name=task_name_input.strip(),
                    duration_minutes=int(duration_input),
                    priority=int(priority_input),
                    category=category_input,
                )
                selected_pet.add_task(new_task)
                owner.save_to_json()
                st.session_state["scheduler"] = _make_scoped_scheduler(owner, selected_pet)
                st.session_state["scheduler"].generate_plan()
                st.success(f"Task '{new_task.name}' added to {selected_pet.name}.")

    current_tasks = selected_pet.get_tasks()
    if current_tasks:
        st.markdown(f"**All tasks for {selected_pet.name}:**")
        st.table(
            [
                {
                    "Task": t.display_name,
                    "Duration (min)": t.duration_minutes,
                    "Priority": t.priority_label,
                    "Category": t.category,
                }
                for t in current_tasks
            ]
        )

st.divider()

# --- Today's Schedule ------------------------------------------------------
st.subheader("Today's Schedule")

scheduler: Scheduler | None = st.session_state["scheduler"]
if scheduler is None or not scheduler.scheduled_tasks:
    st.info("No schedule yet. Add tasks above and a plan will be generated automatically.")
else:
    total = scheduler.get_total_scheduled_duration()
    budget = owner.available_minutes_per_day
    sorted_tasks = scheduler.sort_by_time()
    scheduled_tasks = scheduler.scheduled_tasks

    # Status banners
    conflict_msg = scheduler.detect_conflicts()
    if conflict_msg:
        st.warning(f"⚠️ Scheduling Conflict Detected\n\n{conflict_msg}")
    else:
        st.success("✅ No scheduling conflicts")

    all_done = all(t.is_completed for t in scheduled_tasks)
    high_priority_pending = any(t.priority >= 4 and not t.is_completed for t in scheduled_tasks)

    if all_done:
        st.success("🎉 All scheduled tasks are completed! Great job!")
    elif high_priority_pending:
        high_pending_names = [t.display_name for t in scheduled_tasks if t.priority >= 4 and not t.is_completed]
        st.warning(f"⚠️ High-priority tasks still pending: {', '.join(high_pending_names)}")

    if total <= budget:
        st.success(f"Plan fits within your {budget}-minute daily budget — {total} min used, {budget - total} min remaining.")
    if budget - total <= 10 and total > 0:
        st.warning(f"Schedule is nearly full — only {budget - total} min remaining.")
    st.info(f"{len(sorted_tasks)} task(s) scheduled — {total} / {budget} min used")

    # Schedule table with checkboxes
    st.markdown("**Task Checklist:**")
    hcols = st.columns([3, 2, 1, 2, 1, 2, 2])
    for col, label in zip(hcols, ["Task", "Priority", "Min", "Category", "Time", "Due Date", "Status"]):
        col.markdown(f"**{label}**")

    for task in sorted_tasks:
        cb_key = f"chk_{task.name}"
        due_date = task.next_occurrence() or "One-time"
        status_text = "✅ Done" if task.is_completed else "⏳ Pending"

        rcols = st.columns([3, 2, 1, 2, 1, 2, 2])
        with rcols[0]:
            st.checkbox(
                task.display_name,
                value=task.is_completed,
                key=cb_key,
                on_change=_toggle_task,
                args=(task.name, cb_key),
            )
        rcols[1].markdown(task.priority_label)
        rcols[2].markdown(str(task.duration_minutes))
        rcols[3].markdown(task.category)
        rcols[4].markdown(task.time)
        rcols[5].markdown(due_date)
        rcols[6].markdown(status_text)

    st.divider()

    # Plan explanation inside an expander to avoid cluttering the main view
    explanation_text = scheduler.explain_plan()
    with st.expander("Why was this plan chosen?"):
        st.text(explanation_text)

    scheduled_names = {t.name for t in scheduler.scheduled_tasks}
    excluded_tasks = [
        t
        for pet in scheduler.pets
        for t in pet.get_tasks()
        if not t.is_completed and t.name not in scheduled_names
    ]
    if excluded_tasks:
        st.warning(
            "Tasks excluded due to time constraints: "
            + ", ".join(t.display_name for t in excluded_tasks)
        )

    st.divider()

    # Filtered views
    st.subheader("Filter Schedule")
    filter_choice = st.radio("Show", ["All", "Completed", "Incomplete"], horizontal=True)

    if filter_choice == "Completed":
        filtered = scheduler.filter_by_status(True)
    elif filter_choice == "Incomplete":
        filtered = scheduler.filter_by_status(False)
    else:
        filtered = sorted_tasks

    if filtered:
        st.table(
            [
                {
                    "Task": t.display_name,
                    "Priority": t.priority_label,
                    "Time": t.time,
                    "Duration (min)": t.duration_minutes,
                    "Category": t.category,
                    "Due Date": t.next_occurrence() or "One-time",
                    "Status": "✅ Done" if t.is_completed else "⏳ Pending",
                }
                for t in filtered
            ]
        )
    else:
        st.info(f"No {filter_choice.lower()} tasks to show.")

st.divider()

# --- AI Advisor ------------------------------------------------------------
st.subheader("🤖 AI Pet Care Advisor")
st.markdown("Ask a question about your pets and get AI-powered advice based on your schedule.")

if not owner.get_pets():
    st.info("Add at least one pet above before using the AI Advisor.")
else:
    user_query = st.text_input("Ask the AI advisor anything about your pets:", placeholder="e.g. What should I prioritize for Max today?")

    if st.button("Get Advice"):
        if user_query.strip():
            with st.spinner("Thinking..."):
                result = get_ai_advice(user_query, owner)
                log_interaction(user_query, result)

            if result["flagged"]:
                st.error(f"⚠️ {result['response']}")
            elif result["success"]:
                st.success("✅ AI Advisor Response:")
                st.markdown(result["response"])
                confidence = result["confidence"]
                if confidence >= 0.8:
                    st.info(f"🟢 Confidence: {confidence:.0%}")
                elif confidence >= 0.5:
                    st.warning(f"🟡 Confidence: {confidence:.0%}")
                else:
                    st.error(f"🔴 Confidence: {confidence:.0%} — treat this response with caution.")
            else:
                st.error(f"Something went wrong: {result['response']}")
        else:
            st.warning("Please enter a question first.")
