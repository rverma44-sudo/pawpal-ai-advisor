from datetime import date, timedelta

from pawpal_system import Owner, Pet, Scheduler, Task


def test_task_completion():
    # Verifies that mark_complete() sets is_completed to True and reset() reverses it
    task = Task(name="Morning Walk", duration_minutes=30, priority=5, category="exercise")

    task.mark_complete()
    assert task.is_completed is True, "mark_complete() should set is_completed to True"

    task.reset()
    assert task.is_completed is False, "reset() should set is_completed back to False"


def test_task_addition():
    # Verifies that add_task() appends tasks to a Pet and get_tasks() reflects the correct count
    pet = Pet(name="Max", species="Dog", breed="Labrador Retriever", age_years=3)

    pet.add_task(Task(name="Feeding", duration_minutes=10, priority=5, category="nutrition"))
    assert len(pet.get_tasks()) == 1, "Pet should have exactly 1 task after the first add_task() call"

    pet.add_task(Task(name="Enrichment Play", duration_minutes=20, priority=4, category="enrichment"))
    assert len(pet.get_tasks()) == 2, "Pet should have exactly 2 tasks after the second add_task() call"


# ═══════════════════════════════════════
# PART 1: CORE BEHAVIOR TESTS
# ═══════════════════════════════════════


def test_generate_plan_fits_budget_and_orders_by_priority():
    """Verifies generate_plan() skips tasks that exceed the budget and returns included tasks in priority-descending order."""
    owner = Owner("Sam", "sam@test.com", available_minutes_per_day=50)
    pet = Pet("Rex", "dog", "lab", 3)
    owner.add_pet(pet)
    # Walk(30 min, p5) added first → time_used = 30
    # Bath(30 min, p4) would push to 60 > 50 → skipped
    # Feed(10 min, p3) brings total to 40 ≤ 50 → added
    pet.add_task(Task("Walk", 30, priority=5, category="exercise"))
    pet.add_task(Task("Bath", 30, priority=4, category="grooming"))
    pet.add_task(Task("Feed", 10, priority=3, category="nutrition"))
    scheduler = Scheduler(owner)

    result = scheduler.generate_plan()

    assert len(result) == 2, "Only Walk and Feed should fit within the 50-minute budget"
    assert result[0].name == "Walk", "Walk (priority 5) should be first in the plan"
    assert result[1].name == "Feed", "Feed (priority 3) should be second after Bath is excluded"
    assert all(t.name != "Bath" for t in result), "Bath (30 min) must be excluded because it would exceed the budget"


def test_mark_complete_sets_flag_and_advances_due_date():
    """Verifies mark_complete() sets is_completed=True and advances due_date by 1 day (daily) or 7 days (weekly)."""
    daily_task = Task("Morning Meds", 10, priority=3, category="health", frequency="daily")
    weekly_task = Task("Flea Treatment", 15, priority=4, category="health", frequency="weekly")

    daily_task.mark_complete()
    weekly_task.mark_complete()

    assert daily_task.is_completed is True, "daily task should have is_completed set to True"
    assert daily_task.due_date == date.today() + timedelta(days=1), \
        "daily task due_date should advance by exactly 1 day"
    assert weekly_task.is_completed is True, "weekly task should have is_completed set to True"
    assert weekly_task.due_date == date.today() + timedelta(weeks=1), \
        "weekly task due_date should advance by exactly 7 days"


def test_detect_conflicts_returns_warning_for_shared_time():
    """Verifies detect_conflicts() returns a non-None string containing both task names when two tasks share a time."""
    owner = Owner("Sam", "sam@test.com", available_minutes_per_day=999)
    pet = Pet("Rex", "dog", "lab", 3)
    owner.add_pet(pet)
    pet.add_task(Task("Walk", 20, priority=5, category="exercise", time="09:00"))
    pet.add_task(Task("Bath", 30, priority=4, category="grooming", time="09:00"))
    scheduler = Scheduler(owner)
    scheduler.generate_plan()

    result = scheduler.detect_conflicts()

    assert result is not None, "detect_conflicts() should return a warning string, not None, for a shared time slot"
    assert "09:00" in result, "The warning must include the conflicting time '09:00'"
    assert "Walk" in result, "The warning must include the name 'Walk'"
    assert "Bath" in result, "The warning must include the name 'Bath'"


def test_sort_by_time_returns_chronological_order_without_mutating():
    """Verifies sort_by_time() returns tasks ordered chronologically and does not mutate scheduled_tasks."""
    owner = Owner("Sam", "sam@test.com", available_minutes_per_day=999)
    pet = Pet("Rex", "dog", "lab", 3)
    owner.add_pet(pet)
    # Inserted as "14:00", "08:00", "11:30" per spec; priorities invert time order so
    # generate_plan() produces [14:00, 11:30, 08:00] — making the mutation check meaningful.
    pet.add_task(Task("Afternoon Walk", 20, priority=5, category="exercise", time="14:00"))
    pet.add_task(Task("Morning Meds", 10, priority=3, category="health", time="08:00"))
    pet.add_task(Task("Midday Feed", 15, priority=4, category="nutrition", time="11:30"))
    scheduler = Scheduler(owner)
    scheduler.generate_plan()
    # generate_plan() orders by priority desc → [14:00, 11:30, 08:00]
    original_names = [t.name for t in scheduler.scheduled_tasks]

    result = scheduler.sort_by_time()

    assert [t.time for t in result] == ["08:00", "11:30", "14:00"], \
        "sort_by_time() must return tasks in chronological order"
    assert [t.name for t in scheduler.scheduled_tasks] == original_names, \
        "sort_by_time() must not mutate the original scheduled_tasks list"


def test_mark_task_complete_adds_recurrence_to_pet():
    """Verifies completing a daily recurring task adds exactly one new Task to the pet with is_completed=False and the correct due_date."""
    owner = Owner("Sam", "sam@test.com", available_minutes_per_day=999)
    pet = Pet("Rex", "dog", "lab", 3)
    owner.add_pet(pet)
    pet.add_task(Task("Morning Meds", 10, priority=5, category="health", frequency="daily"))
    scheduler = Scheduler(owner)
    scheduler.generate_plan()
    count_before = len(pet.get_tasks())

    scheduler.mark_task_complete("Morning Meds")

    tasks_after = pet.get_tasks()
    assert len(tasks_after) == count_before + 1, \
        "Completing a daily task should add exactly one new occurrence to the pet"
    new_task = tasks_after[-1]
    assert new_task.is_completed is False, \
        "The new occurrence must have is_completed=False"
    assert new_task.due_date == date.today() + timedelta(days=1), \
        "The new occurrence should have due_date set to today + 1 day"


def test_recurrence_logic():
    """Verifies mark_complete() advances due_date by one day for a daily task, and mark_task_complete() adds exactly one new incomplete occurrence to the pet."""
    owner = Owner("Sam", "sam@test.com", available_minutes_per_day=999)
    pet = Pet("Rex", "dog", "lab", 3)
    owner.add_pet(pet)
    task = Task("Morning Meds", 10, priority=5, category="health", frequency="daily")
    pet.add_task(task)
    scheduler = Scheduler(owner)
    scheduler.generate_plan()

    task.mark_complete()

    assert task.due_date == date.today() + timedelta(days=1), \
        "mark_complete() on a daily task must set due_date to today + 1 day"

    count_before = len(pet.get_tasks())
    scheduler.mark_task_complete("Morning Meds")
    tasks_after = pet.get_tasks()

    assert len(tasks_after) == count_before + 1, \
        "mark_task_complete() must add exactly one new occurrence to the pet"
    assert tasks_after[-1].is_completed is False, \
        "The new occurrence must have is_completed set to False"


# ═══════════════════════════════════════
# PART 2: HAPPY PATH TESTS
# ═══════════════════════════════════════


def test_all_tasks_fit_within_budget():
    """Verifies all three tasks are scheduled when their combined duration (100 min) is within the 120-minute budget."""
    owner = Owner("Sam", "sam@test.com", available_minutes_per_day=120)
    pet = Pet("Rex", "dog", "lab", 3)
    owner.add_pet(pet)
    pet.add_task(Task("Walk", 40, priority=5, category="exercise"))
    pet.add_task(Task("Feed", 30, priority=4, category="nutrition"))
    pet.add_task(Task("Play", 30, priority=3, category="enrichment"))
    scheduler = Scheduler(owner)

    result = scheduler.generate_plan()

    assert len(result) == 3, "All 3 tasks (100 min total) should be scheduled within the 120-minute budget"
    assert {t.name for t in result} == {"Walk", "Feed", "Play"}, \
        "The scheduled plan must contain exactly Walk, Feed, and Play"


def test_daily_task_due_date_advances_one_day():
    """Verifies that mark_complete() on a daily task sets due_date to exactly today plus one day."""
    task = Task("Daily Brush", 10, priority=2, category="grooming", frequency="daily")

    task.mark_complete()

    assert task.due_date == date.today() + timedelta(days=1), \
        "Daily task due_date must be today + 1 day after mark_complete()"


def test_weekly_task_due_date_advances_seven_days():
    """Verifies that mark_complete() on a weekly task sets due_date to exactly today plus seven days."""
    task = Task("Flea Treatment", 20, priority=4, category="health", frequency="weekly")

    task.mark_complete()

    assert task.due_date == date.today() + timedelta(weeks=1), \
        "Weekly task due_date must be today + 7 days after mark_complete()"


def test_chronological_sort():
    """Verifies sort_by_time() returns tasks in the order 08:00, 11:30, 14:00 regardless of insertion order."""
    owner = Owner("Sam", "sam@test.com", available_minutes_per_day=999)
    pet = Pet("Rex", "dog", "lab", 3)
    owner.add_pet(pet)
    pet.add_task(Task("Afternoon Walk", 20, priority=3, category="exercise", time="14:00"))
    pet.add_task(Task("Morning Meds", 10, priority=5, category="health", time="08:00"))
    pet.add_task(Task("Midday Feed", 15, priority=4, category="nutrition", time="11:30"))
    scheduler = Scheduler(owner)
    scheduler.generate_plan()

    result = scheduler.sort_by_time()

    assert [t.time for t in result] == ["08:00", "11:30", "14:00"], \
        "Tasks inserted as 14:00 → 08:00 → 11:30 must be sorted to 08:00 → 11:30 → 14:00"


def test_no_conflicts_returns_none():
    """Verifies detect_conflicts() returns None when all scheduled tasks have distinct time values."""
    owner = Owner("Sam", "sam@test.com", available_minutes_per_day=999)
    pet = Pet("Rex", "dog", "lab", 3)
    owner.add_pet(pet)
    pet.add_task(Task("Walk", 20, priority=5, category="exercise", time="08:00"))
    pet.add_task(Task("Feed", 15, priority=4, category="nutrition", time="09:00"))
    scheduler = Scheduler(owner)
    scheduler.generate_plan()

    result = scheduler.detect_conflicts()

    assert result is None, "detect_conflicts() should return None when every task occupies a unique time slot"


# ═══════════════════════════════════════
# PART 3: EDGE CASE TESTS
# ═══════════════════════════════════════


def test_generate_plan_pet_with_no_tasks():
    """Verifies generate_plan() returns an empty list without raising an exception when the pet has no tasks."""
    owner = Owner("Sam", "sam@test.com", available_minutes_per_day=60)
    pet = Pet("Ghost", "cat", "siamese", 2)
    owner.add_pet(pet)
    scheduler = Scheduler(owner)

    result = scheduler.generate_plan()

    assert result == [], "generate_plan() must return [] when the pet has no tasks assigned"


def test_detect_conflicts_exact_time_match():
    """Verifies detect_conflicts() returns a warning with '09:00' and both task names when two tasks share that exact time."""
    owner = Owner("Sam", "sam@test.com", available_minutes_per_day=999)
    pet = Pet("Rex", "dog", "lab", 3)
    owner.add_pet(pet)
    pet.add_task(Task("Walk", 20, priority=5, category="exercise", time="09:00"))
    pet.add_task(Task("Bath", 30, priority=4, category="grooming", time="09:00"))
    scheduler = Scheduler(owner)
    scheduler.generate_plan()

    result = scheduler.detect_conflicts()

    assert result is not None, "detect_conflicts() must return a non-None warning for two tasks at 09:00"
    assert "09:00" in result, "Warning must contain the shared time slot '09:00'"
    assert "Walk" in result, "Warning must contain the task name 'Walk'"
    assert "Bath" in result, "Warning must contain the task name 'Bath'"


def test_mark_task_complete_unknown_name_returns_warning():
    """Verifies mark_task_complete() returns a non-None warning string without raising when the name is not in scheduled_tasks."""
    owner = Owner("Sam", "sam@test.com", available_minutes_per_day=999)
    pet = Pet("Rex", "dog", "lab", 3)
    owner.add_pet(pet)
    pet.add_task(Task("Walk", 20, priority=5, category="exercise"))
    scheduler = Scheduler(owner)
    scheduler.generate_plan()

    result = scheduler.mark_task_complete("no_such_task")

    assert result is not None, "mark_task_complete() should return a warning string for an unknown task name"
    assert "no_such_task" in result, "The warning string must contain the unrecognised task name"


def test_once_task_does_not_recur_after_completion():
    """Verifies that completing a frequency='once' task neither adds a new task to the pet nor changes due_date."""
    owner = Owner("Sam", "sam@test.com", available_minutes_per_day=999)
    pet = Pet("Rex", "dog", "lab", 3)
    owner.add_pet(pet)
    fixed_date = date(2025, 6, 15)
    task = Task("Vet Checkup", 60, priority=5, category="health", frequency="once", due_date=fixed_date)
    pet.add_task(task)
    scheduler = Scheduler(owner)
    scheduler.generate_plan()
    count_before = len(pet.get_tasks())

    scheduler.mark_task_complete("Vet Checkup")

    assert len(pet.get_tasks()) == count_before, \
        "Completing a frequency='once' task must not add a new occurrence to the pet"
    assert task.due_date == fixed_date, \
        "due_date must remain unchanged after completing a one-time task"


def test_filter_by_status_empty_scheduled_tasks():
    """Verifies filter_by_status() returns an empty list without raising when scheduled_tasks is empty."""
    owner = Owner("Sam", "sam@test.com", available_minutes_per_day=60)
    scheduler = Scheduler(owner)
    # generate_plan() is intentionally not called so scheduled_tasks stays []

    result_incomplete = scheduler.filter_by_status(False)
    result_complete = scheduler.filter_by_status(True)

    assert result_incomplete == [], \
        "filter_by_status(False) must return [] when scheduled_tasks is empty"
    assert result_complete == [], \
        "filter_by_status(True) must return [] when scheduled_tasks is empty"


def test_generate_plan_budget_smaller_than_every_task():
    """Verifies generate_plan() returns an empty list when every task's duration exceeds the owner's available budget."""
    owner = Owner("Sam", "sam@test.com", available_minutes_per_day=5)
    pet = Pet("Rex", "dog", "lab", 3)
    owner.add_pet(pet)
    pet.add_task(Task("Walk", 10, priority=5, category="exercise"))
    pet.add_task(Task("Bath", 20, priority=4, category="grooming"))
    scheduler = Scheduler(owner)

    result = scheduler.generate_plan()

    assert result == [], "generate_plan() must return [] when every task exceeds the 5-minute budget"
    assert scheduler.get_total_scheduled_duration() == 0, \
        "Total scheduled duration must be 0 when no tasks can be scheduled"
