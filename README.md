# Data Jobs Scanner: Workday + Greenhouse + Lever + Ashby (whole US, hourly)

Runs on its own every hour in GitHub Actions. Each run:
1. **Finds companies** (once a day): Google (SerpAPI) finds companies posting US data jobs on all 4 platforms and adds them to `companies.txt`.
2. **Scans every board** for new US data jobs: analyst / scientist / engineer / ML / BI, posted today or yesterday, no senior/manager/intern titles.
3. **Scores each job** against your resumes and fills in Match %, Best Resume (DA/DE/DS), Sponsorship, Years Req, and Matched/Missing Skills.
4. **Tailors your resume with Claude** for the top matches (up to 10 per run) and saves them in `tailored/<date>/`, linked from Excel.
5. **Emails you** top matches first, with `jobs.xlsx` and the tailored resume PDFs attached.

### How resume tailoring works
It follows the **Wonsulting Resume Playbook**:
- **6-second test:** relevant experience and skills come first.
- **HAMS bullets:** each bullet has a Hard skill, a strong Action verb and a Metric, structured as skill → action → context → impact.
- **Job-description mirroring:** the skills section uses the job's own wording.
- **Format:** no summary, and Education comes first (student format).

Claude can only **choose, reorder and reword** content from `resumes/resume_master.json`, which holds every true bullet, project and skill from your 3 resumes. The code then checks each bullet: if it contains a number or tool that isn't in your original text, it's swapped back to your original wording. **Nothing made up can reach the PDF.**

When you gain new experience, add it to `resumes/resume_master.json` (and replace the PDFs in `resumes/` so match scoring updates too).

It also maintains itself:
- **Broken board links** get switched off after 3 failed runs in a row.
- **Updated resumes:** replace the PDFs in `resumes/` (keep DA / DE / DS in the file names) and the skill profiles rebuild on the next run.
- **Seen jobs** are remembered, so you never get the same job twice.

## Setup (one time, ~5 minutes)
You need:
- a **SerpAPI key** (serpapi.com)
- a **Claude API key** (console.anthropic.com; billed separately from a Claude.ai subscription, about a few cents per tailored resume)
- a **Gmail app password** (Google Account → Security → 2-Step Verification → App passwords)

**Option A: terminal** (needs the GitHub CLI, `brew install gh`):
```bash
git clone https://github.com/khus-hi/shreeGanesh.git
cd shreeGanesh
bash setup.sh
```

**Option B: browser only:**
1. Repo → **Settings → Secrets and variables → Actions → New repository secret**. Add `SERPAPI_KEY`, `ANTHROPIC_API_KEY`, `GMAIL_USER`, `GMAIL_APP_PASSWORD` and `ALERT_EMAIL_TO`.
2. Repo → **Actions** tab → enable workflows → **Workday job scan → Run workflow**.

After that it runs every hour by itself.

## Optional tweaks (top of `workday_jobs.py`)
- `MIN_MATCH_FOR_ALERT = 60`: what counts as a top match
- `SKIP_NO_SPONSORSHIP = False`: True drops "no sponsorship" jobs entirely
- `MAX_TAILORED_PER_RUN = 10`: cap on Claude resumes per run (controls cost)
- Claude model: set a `CLAUDE_MODEL` env var in the workflow to change it (default `claude-sonnet-5-5`)
- `TITLE_EXCLUDE`: remove `senior|` etc. to include those roles
- `INCLUDE_REMOTE = True`: keep remote-US jobs
- H-1B History column: fills in only if you add a USCIS H-1B Employer Data Hub CSV as `h1b_employers.csv`

## Limits
- This repo is **public**: resumes, `jobs.xlsx` and tailored resumes are visible to anyone. Public repos get unlimited free Actions minutes.
- Match % is keyword-based. Use it to rank jobs, not as a final answer.
