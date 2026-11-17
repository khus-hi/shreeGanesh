# Data Jobs Scanner: Workday + Greenhouse + Lever + Ashby (whole US, hourly)

Runs on its own every hour in GitHub Actions. Each run:
1. **Finds companies** (once a day): Google (SerpAPI) finds companies posting US data jobs on all 4 platforms and adds them to `companies.txt`.
2. **Scans every board** for new US data jobs: analyst / scientist / engineer / ML / BI, posted today or yesterday, no senior/manager/intern titles.
3. **Scores each job** against your resumes and fills in Match %, Best Resume (DA/DE/DS), Sponsorship, Years Req, and Matched/Missing Skills.
4. **Tailors your resume with Claude** for the top matches (up to 10 per run) and saves them in `tailored/<date>/`, linked from Excel.
5. **Updates your dashboard** at https://khus-hi.github.io/shreeGanesh/ and **emails you** top matches with a link to it.

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

## Job dashboard (website)
**https://khus-hi.github.io/shreeGanesh/** updates itself every hour and works on your phone too.
- **Views:** All, New (24h), Top matches, Saved, Applied, Interviewing, Offers, Rejected, Hidden.
- **Filters:** search, which resume, state, tech-hub metro, sponsorship, minimum match %, and sort order.
- **Each job:** match score, which resume to send, sponsorship, years required, your matched and missing skills, and an **Apply** button.
- **Status tracking:** set each job to New / Saved / Applied / Interview / Offer / Rejected / Hidden. Statuses are saved in your browser; use **Back up statuses / Restore statuses** at the bottom to move them to another device.
- **Download CSV** of whatever you're currently viewing.

`jobs.xlsx` is still saved in the repo as a backup.

### Keep it private (just for you)
1. **Password-lock the dashboard:** add a repo secret `DASHBOARD_PASSWORD` with any password you choose. The job data is then encrypted (AES-256) and the page shows only a password box until you unlock it. Tick "Remember on this device" so you only type it once per device.
2. **Make the repo private:** **Settings → General → Danger Zone → Change visibility → Private**. This hides your resumes and `jobs.xlsx`.
3. **Keep the dashboard working on a private repo:** GitHub Pages on private repos needs **GitHub Pro**, which is free for students through the **GitHub Student Developer Pack** (education.github.com/pack). The page itself stays reachable by link, but without your password it shows nothing.

## Google Sheet (optional)
Every run adds new jobs to a Google Sheet: newest on top, top matches green, "No sponsorship" in red. Your edits, like the Status column, are never overwritten. One-time setup, about 3 minutes:
1. Create a new Google Sheet (sheets.new) and name it e.g. **Job Scanner**.
2. **Extensions → Apps Script**. Delete everything there, paste the contents of `google_sheets_script.gs`, and click **Save**.
3. **Deploy → New deployment →** gear icon **→ Web app**. Set *Execute as*: **Me** and *Who has access*: **Anyone**. Click **Deploy**, then **Authorize access** and allow it. If it says "Google hasn't verified this app", click **Advanced → Go to … (unsafe)**; it's your own script.
4. Copy the **Web app URL** (ends in `/exec`).
5. In the GitHub repo, go to **Settings → Secrets and variables → Actions → New repository secret**. Name: `SHEETS_WEBHOOK_URL`, value: the URL.

The next run fills the sheet, including all jobs found so far. Test the link by opening the URL in your browser; it should say "Job scanner sheet is connected."

## Optional tweaks (top of `workday_jobs.py`)
- `MIN_MATCH_FOR_ALERT = 60`: what counts as a top match
- `SKIP_NO_SPONSORSHIP = False`: True drops "no sponsorship" jobs entirely
- `MAX_TAILORED_PER_RUN = 10`: cap on Claude resumes per run (controls cost)
- Claude model: set a `CLAUDE_MODEL` env var in the workflow to change it (default `claude-sonnet-5-5`)
- `TITLE_EXCLUDE`: remove `senior|` etc. to include those roles
- `INCLUDE_REMOTE = True`: keep remote-US jobs
- H-1B History column: fills in only if you add a USCIS H-1B Employer Data Hub CSV as `h1b_employers.csv`

## Limits
- If the repo is **public**, resumes and `jobs.xlsx` are visible to anyone (see *Keep it private*). Private repos get a monthly Actions-minutes allowance (2,000 on Free, 3,000 on Pro); hourly runs use roughly 1–3 minutes each.
- Match % is keyword-based. Use it to rank jobs, not as a final answer.
