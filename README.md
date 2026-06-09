[README-SETUP.md](https://github.com/user-attachments/files/28770775/README-SETUP.md)
# Huntr — automation & hosting setup (for agudoal)

This turns Huntr into a tool that **refreshes itself every night (~03:00 UK)** and lives at a web address you can open on your laptop, iPad or iPhone. You do this once; after that it runs on its own. No coding — just uploading files and clicking a few settings.

**What's in this folder**
- `pipeline.py` — fetches the data and scores every company (the validated v2 logic, now reading `universe.csv`).
- `universe.csv` — the company list (~95 EMEA tech names; edit this file to add/remove names later).
- `build_index.py` — drops the fresh scores into the tool and produces the web page (`index.html`).
- `nightly.yml` — the schedule that runs it all at 03:00.
- This guide.

---

## One-time setup (~15 minutes)

### 1. Create the repository
- Go to **github.com → New repository**. Name it **`huntr`**.
- Set it to **Public** (free hosting needs this — the *code* and *market data* will be visible, but your EODHD key stays secret; we'll do a private URL in the later session).
- Tick **"Add a README"** and create it.

### 2. Upload the files
In the repo, click **Add file → Upload files**, and upload from this folder:
- `pipeline.py`
- `universe.csv`
- `build_index.py`
- **Your tool**, renamed to **`template.html`** — copy `01. Tool/huntr-prototype.html` from your Drive and rename it `template.html` before uploading.

Then the workflow file, which must sit in a special folder:
- Click **Add file → Create new file**, and in the name box type exactly: **`.github/workflows/nightly.yml`** (GitHub will create the folders as you type the `/`).
- Paste the contents of `nightly.yml` from this folder, and commit.

### 3. Add your EODHD key as a secret
- Repo **Settings → Secrets and variables → Actions → New repository secret**.
- Name: **`EODHD_API_KEY`** — Value: *your EODHD key*. Save. (It's encrypted; it never appears in the code or the page.)

### 4. Turn on the website
- Repo **Settings → Pages**.
- Under **Source**, choose **Deploy from a branch**, branch **`main`**, folder **`/ (root)`**. Save.

### 5. Run it once to test
- Go to the **Actions** tab → **Huntr nightly** → **Run workflow** → **Run**.
- Wait ~2–3 minutes (it fetches ~95 names). When the tick goes green, your page is live at:

  **https://agudoal.github.io/huntr/**

Open it on your phone/iPad too. From now on it refreshes automatically every night.

---

## Notes & gotchas
- **Timing:** the cron runs at 02:00 UTC = **03:00 UK in summer**, 02:00 UK in winter. Tell me if you want it pinned differently.
- **Auto-disable:** GitHub pauses scheduled jobs after **60 days of no repo activity** — the nightly commit keeps it awake, so this won't bite in normal use.
- **Editing the universe:** open `universe.csv` in the repo, click the pencil, add a row (`name,ticker,region,subsector,active`), commit. Next run picks it up.
- **Coverage column:** if a name shows low coverage in the tool, its Yahoo ticker is probably slightly off — send it to me and I'll fix it.
- **First run:** since I can't test GitHub from my side, treat the first run as a shakedown — if anything errors, copy me the red log from the Actions tab and I'll sort it.
