# Contribution Garden

A transparent procedural-art generator for the public, standalone repository
`rverma44-sudo/pawpal-ai-advisor`. Every generated commit changes an SVG mosaic
and its small Git-tracked state file. It makes no claim to improve application
code. The older PawPal app can remain alongside it; it is never imported or run
by this workflow.

## Daily operation

`.github/workflows/contribution-garden.yml` runs once every day, including
weekends, at **10:17 AM America/Phoenix**. GitHub may delay or occasionally drop
scheduled jobs; a cron schedule is not an exact-time delivery guarantee.
The generation date and Git timestamps both use America/Phoenix. No dates are
backdated, and missed historical days are never filled in.

The job uses an Ubuntu runner's existing Python 3 and Git. It has one step,
no third-party Actions, no dependency installation, no builds, no AI calls,
no recurring tests, and no external APIs. It shallow-clones this one repository,
fetches its current main, produces the entire batch, pushes once, and independently
checks the remote main SHA. Only the built-in ephemeral GITHUB_TOKEN is needed;
its contents-write permission is scoped to this job. Existing repository secrets
and security settings are not changed. No push trigger causes recursive runs.

## Probability settings

Edit `gardener/config.json`; no Python rewrite is needed. Weights may be fractional and must total 100
and counts are limited to 0–14. The defaults are:

| Category | Probability | Commits |
| --- | ---: | ---: |
| none | 44% | 0 |
| light | 21% | 1–2 |
| moderate | 21% | 3–5 |
| heavy | 10.5% | 6–9 |
| very_heavy | 3.5% | 10–14 |

The active-day probability is 56%, down from the original 80% by a single 0.70
factor. All active category weights were scaled equally; the distribution and
count ranges conditional on an active day are unchanged. No extra probability
gate or scheduling reduction is applied.

A SHA-256 seed of the configured seed and current local date drives the daily
pseudorandom choice; reruns cannot redraw a different outcome. Each count within
a category is equally likely. The mean is 2.3625 generated commits per calendar
day, about 71 per 30 days, subject to successful execution. It is a probability
distribution, not a guarantee of particular colors or daily counts.

`gardener/state.json` is committed with every generated frame and holds the last
active date, selected target, completed count, and global frame counter. A completed
day is never repeated, even after changing configuration. Zero-activity days make
no state commit, so they really contain zero generator commits; their repeated
selection is deterministic. Do not delete/reset state to obtain another run.

## Failure and retry behavior

Actions concurrency serializes scheduled, manual, and rerun invocations.
Only main and the exact authorized fetch/push remote are accepted. Dirty trees,
unexpected unpublished commits, corrupt state, forks, private repositories,
default-branch changes, backward clocks, and mid-session date changes fail closed.

A push is successful only when the remote main SHA independently matches the
local head. A rejected or unverifiable push fails the workflow, leaving local
commits intact. Retry with Actions **Re-run failed jobs** or a new manual dispatch.
A fresh runner reads the durable remote state and regenerates only missing work.
If the first push actually succeeded but its response was lost, the new run sees
the completed state and makes no duplicate commits. A retained local checkout can
also publish only its verified gardener commits. No force-push, reset, rebase,
amend, or automatic unbounded retry is used. Runner-local unpublished commits
disappear when the ephemeral runner is destroyed; their deterministic frames can
be regenerated from remote state.

## Attribution and activation

Both author and committer are explicitly `rverma44-sudo <rverma44@asu.edu>`.
Eligibility was checked at setup: public non-fork repository, main default branch,
and email verified on the owner's account. Keep this email associated with your
GitHub account. Runtime checks use the already-provided workflow event metadata
for repository eligibility; they do not spend API requests rechecking your email.

GitHub documents the [contribution criteria](https://docs.github.com/en/account-and-profile/reference/profile-contributions-reference)
and may take up to 24 hours to process the profile graph. A confirmed push proves
delivery; a profile contribution API result proves graph credit.

Actions automatically disables public schedules after 60 days without repository
activity. The default 56% activity-day model should keep the repository active,
but changing settings to prolonged inactivity or enduring failures may require
re-enabling the workflow. No auxiliary keepalive commits override zero-day choices.

## Commands

```sh
# Read-only local preview, after cloning this repository on main:
python3 gardener/generate.py --dry-run

# One-time focused validation (only temporary local Git repositories):
python3 -m unittest discover -s gardener -p 'test_*.py' -q

# Manual normal run or a non-writing preview:
gh workflow run contribution-garden.yml --repo rverma44-sudo/pawpal-ai-advisor --ref main
gh workflow run contribution-garden.yml --repo rverma44-sudo/pawpal-ai-advisor --ref main -f dry_run=true

# Inspect status and logs:
gh workflow view contribution-garden.yml --repo rverma44-sudo/pawpal-ai-advisor
gh run list --repo rverma44-sudo/pawpal-ai-advisor --workflow contribution-garden.yml --limit 5
gh run view RUN_ID --repo rverma44-sudo/pawpal-ai-advisor --log

# Disable / re-enable:
gh workflow disable contribution-garden.yml --repo rverma44-sudo/pawpal-ai-advisor
gh workflow enable contribution-garden.yml --repo rverma44-sudo/pawpal-ai-advisor
```

The expected baseline is roughly 30–31 short jobs per month, usually seconds per
job (three-minute timeout). Standard hosted runners for this public repository
are [free](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
There are no retained Actions artifacts or billable external services.
