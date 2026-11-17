# Daily process

A routine for running a job search with this tracker. It takes 30 to 60 minutes a day. The tool keeps the
records and the reminders; every decision and every submission stays with you.

## Principles

- **The human decides and submits.** The tracker never applies to anything. If you use any automation to fill
  forms, you read the filled form and press submit yourself, every time. Automation never types or stores your
  passwords; you sign in to every site yourself.
- **Quality over volume.** A short, honest list of criteria (role, level, location, skills overlap) beats applying
  to everything. Write your criteria down once, in your own notes, and check each role against them before applying.
- **Log everything, the same day.** The report is only as good as the log. A role you looked at and skipped can go
  in your notes; a role you applied to goes in the tracker.
- **Respect the sites.** Use each site's normal apply flow, keep a human pace, and stop when a site shows a limit,
  a CAPTCHA or a warning. Never pay for "featured applicant" upsells you did not plan for.

## Morning (10 minutes): replies and reminders

1. Read new messages and emails from employers and recruiters.
2. Record every reply as a status move, with the date it arrived:

   ```bash
   jobtracker status 12 screen --on 2026-01-14 --note "recruiter call Thursday"
   jobtracker status 7 rejected
   ```

3. See what needs a nudge:

   ```bash
   jobtracker due
   ```

4. For each due item, decide: follow up (write the message yourself), snooze, or let it go.

   ```bash
   jobtracker followed-up 12          # you sent a follow-up; next reminder in the configured interval
   jobtracker followed-up 9 --days 5  # snooze five days
   ```

## Midday (20 to 40 minutes): find and apply

1. Search your usual sources, newest first. Skip anything already in the tracker; `jobtracker add` also refuses
   duplicates (same company and title, however spelled, or the same job URL) and tells you the existing id.
2. For each role that meets your criteria, tailor what the role asks for, review it, and submit it yourself.
3. Log it straight away:

   ```bash
   jobtracker add "Example Co" "Data Scientist" --source job-board --url https://jobs.example.com/123
   ```

   If `add` prints "similar entries", look at them: a close spelling may be the same role.

4. Long external forms that need a fresh account or many free-text answers: put them in your notes for a focused
   session rather than rushing them.

## Evening (5 minutes): tidy

```bash
jobtracker ghost        # applications with no reply after ghost_after_days become "ghosted"
jobtracker list --status interview
```

Prepare for the next day's interviews from that list.

## Weekly (15 minutes): look at traction

```bash
jobtracker report --week-of 2026-01-12 --out reports/2026-01-12.md
```

Read it with two questions:

- **Which sources reply?** If referrals reply at three times the rate of job boards, spend more of the week on
  referrals.
- **Which role types reply?** A role type with many applications and no replies is a signal to change the CV, the
  level you aim at, or the role type.

Small numbers move a lot. Three replies out of five is not a trend; wait for a few weeks of data before changing
course. Applications younger than the minimum age (default seven days) are shown as "too new" and left out of the
rates, so a busy week does not look like a bad one.

## If you automate parts of it

Browser automation can save time on searching and on filling repetitive fields. Keep these rules:

- You approve every submission. The automation stops before the final submit and waits for you.
- The automation never enters, stores or reads passwords. You sign in yourself; it works only in a session you
  opened.
- It follows the site's normal pace and stops on any limit, CAPTCHA or warning.
- It logs through `jobtracker add` like you would, so de-duplication and the report still work.
- It never sends messages to people on your behalf.

## Keeping your data private

`tracker.db`, CSV exports and your own `jobtracker.toml` are git-ignored. Keep personal details, pay details and
the names of the people you talk to out of the `notes` field if you ever share an export.
