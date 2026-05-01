# Shipment Tracker

A private web app for your team to track shipments across **UPS, FedEx, Day & Ross, and Polaris Transport** from one place. Enter a tracking number, see the status, location, and full event history — no need to visit each carrier's website.

---

## How It Works (Plain English)

Think of this app as a middleman:

1. You enter a tracking number in the app
2. The app quietly opens the carrier's website in the background (like a robot using a web browser)
3. It reads the tracking information and shows it to you in a clean, consistent format
4. It automatically refreshes tracking info every 6 hours so you always have the latest status

The app has two parts:
- **Backend** — the engine that does the tracking lookups. Runs as a program on a computer or server.
- **Frontend** — the website you see and click on. Can be hosted for free anywhere.

---

## Before You Start — What You Need

Install these three programs on the computer that will run the app. Click each link, download, and install with default settings:

| Program | Where to get it | Why it's needed |
|---------|----------------|-----------------|
| **Python 3.12** | [python.org/downloads](https://www.python.org/downloads/) | Runs the backend engine |
| **Node.js 20+** | [nodejs.org](https://nodejs.org/) (choose "LTS" version) | Builds the website frontend |
| **Git** | [git-scm.com/downloads](https://git-scm.com/downloads) | Downloads the code from GitHub |

> **Windows users:** When installing Python, tick the box **"Add Python to PATH"** before clicking Install. This is important.

---

## Step 1 — Download the Code

Open **Command Prompt** (press `Windows key`, type `cmd`, press Enter) and run this command to download the code:

```
git clone https://github.com/NayanSpace/Tracking-Shipments-.git
cd Tracking-Shipments-
```

You now have a folder called `Tracking-Shipments-` on your computer with all the code inside.

---

## Step 2 — Set Up the Free Database

The app needs a database to remember tracking numbers. We use **Neon.tech** — it's free, no credit card required, and never expires.

1. Go to **[neon.tech](https://neon.tech)** and click **Sign Up** (you can sign in with Google)
2. Click **New Project**, give it any name (e.g. `shipping-tracker`), click **Create**
3. On the next screen, look for **Connection string** — it looks like:
   ```
   postgresql://neondb_owner:somepassword@ep-something.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
4. Click the **copy** button next to it — you'll need this in Step 3

---

## Step 3 — Configure the App

Inside the `Tracking-Shipments-` folder, find the file called `.env.example`. Make a copy of it and rename the copy to `.env` (remove the `.example` part).

Open the `.env` file with Notepad and fill in these values:

```
DATABASE_URL=paste-your-neon-connection-string-here

SECRET_KEY=any-long-random-string-of-letters-and-numbers-at-least-32-chars

APP_USERNAME=the-username-your-team-will-use-to-log-in
APP_PASSWORD=the-password-your-team-will-use-to-log-in

ENVIRONMENT=production
FRONTEND_URL=http://localhost:5173
```

**For `SECRET_KEY`:** Just type a long random string — like `mycompanyshippingtracker2026secretxyz789abc`. It just needs to be unique and at least 32 characters. Nobody ever types this in; it's used internally for security.

**For `APP_USERNAME` and `APP_PASSWORD`:** Pick whatever login credentials you want your team to use. Everyone shares the same login.

Save and close the file.

---

## Step 4 — Install the App's Dependencies

Still in Command Prompt, run these commands one at a time. Each one may take a few minutes:

```
cd backend
pip install -r requirements.txt
playwright install chromium
playwright install chrome
cd ..
```

```
cd frontend
npm install
cd ..
```

> If you get a "pip not found" error, try `python -m pip install -r requirements.txt` instead.

---

## Step 5 — Set Up the Database Tables

Run this once to create the tables in your Neon database:

```
cd backend
alembic upgrade head
cd ..
```

You should see a message like `Running upgrade ... -> ...`. That means it worked.

---

Now choose how you want to host the app. **Option A** is recommended if you want all 4 carriers (including UPS and FedEx) to work.

---

# Option A — Run on Your Computer + Cloudflare Tunnel

**Best for:** Small teams, all 4 carriers working, completely free.

**How it works:** The app runs on a PC in your office. Cloudflare creates a public web address that anyone on your team can visit, even from home. As long as that PC is on, the app is accessible.

**Trade-off:** If the PC is turned off, the app is unavailable.

---

### A1 — Start the Backend

Open a **new Command Prompt window** and run:

```
cd Tracking-Shipments-\backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Leave this window open. You should see:
```
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:8000
```

### A2 — Start the Frontend

Open another **new Command Prompt window** and run:

```
cd Tracking-Shipments-\frontend
npm run dev
```

Leave this window open too. You should see something like:
```
  VITE v5.x.x  ready
  Local:   http://localhost:5173/
```

You can now open **http://localhost:5173** in your browser to use the app locally. Log in with the `APP_USERNAME` and `APP_PASSWORD` you set.

### A3 — Make It Accessible to Your Team (Cloudflare Tunnel)

To give your team a public link, use Cloudflare Tunnel. It's free and takes 5 minutes to set up.

**Install Cloudflared:**

On Windows, open Command Prompt and run:
```
winget install --id Cloudflare.cloudflared
```

If `winget` is not available, download the installer manually from [developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) — download `cloudflared-windows-amd64.exe`, rename it to `cloudflared.exe`, and place it in `C:\Windows\System32\`.

**Get a quick public link (simplest method — no account needed):**

Open a third Command Prompt window and run:
```
cloudflared tunnel --url http://localhost:8000
```

After about 10 seconds, you'll see something like:
```
Your quick Tunnel has been created! Visit it at:
https://random-words-here.trycloudflare.com
```

That URL is your team's link to the backend. But your frontend also needs to know about it — read the note below.

> **Note on the frontend:** For a proper setup where your team visits one link, you need to build the frontend with the correct backend URL. Before running `npm run dev`, update the `VITE_API_URL` in your `.env` file (or create `frontend/.env.local`) with your Cloudflare URL:
> ```
> VITE_API_URL=https://your-tunnel-url.trycloudflare.com/api
> ```
> Then run `npm run build` (instead of `npm run dev`) and serve the `frontend/dist` folder using a free static host like Render (see Option B for the frontend part only).

**For a permanent URL (recommended for daily use):**

1. Sign up for a free account at [dash.cloudflare.com](https://dash.cloudflare.com) (you can use a free domain or your own domain)
2. Run `cloudflared tunnel login` — it will open a browser to log you in
3. Run `cloudflared tunnel create shipping-tracker`
4. Follow Cloudflare's guide at [developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/) to link it to a hostname

---

# Option B — Railway.app (Cloud Hosting)

**Best for:** Always-on cloud hosting, no PC needs to stay on, ~$5/month or less.

**Important limitation:** UPS and FedEx use a security system (Akamai) that **blocks requests from cloud server IPs**. This is not a bug in the app — it's how UPS and FedEx protect their sites. On any cloud host, UPS and FedEx will likely return errors. **Day & Ross and Polaris work perfectly on cloud.** If your team primarily uses Day & Ross and Polaris, cloud hosting is a great choice.

---

### B1 — Push Your Code to GitHub

If you haven't already, make sure your code is on GitHub at `https://github.com/NayanSpace/Tracking-Shipments-`. The code should already be there if you followed the setup.

### B2 — Create a Railway Account

1. Go to **[railway.app](https://railway.app)** and click **Start a New Project**
2. Sign in with your GitHub account
3. Railway will ask for a **Hobby Plan** at $5/month — you get $5 free credit each month, which typically covers light usage entirely

### B3 — Deploy the Backend

1. Click **New Project** → **Deploy from GitHub repo**
2. Select `NayanSpace/Tracking-Shipments-`
3. Railway will detect the `Dockerfile` in the `backend` folder. If it doesn't auto-detect:
   - Click **Add service** → **GitHub Repo**
   - Under **Settings**, set **Root Directory** to `backend`
4. Go to the service's **Variables** tab and add:

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | Your Neon connection string from Step 2 |
| `SECRET_KEY` | Your secret key from Step 3 |
| `APP_USERNAME` | Your team login username |
| `APP_PASSWORD` | Your team login password |
| `ENVIRONMENT` | `production` |
| `FRONTEND_URL` | You'll add this after the frontend is deployed |

5. Click **Deploy**. The first build takes 10–15 minutes (it's downloading Chrome and all the tools). Subsequent deploys are much faster.

6. Once deployed, go to **Settings** → **Networking** → **Generate Domain**. Copy that URL — it will look like `https://something.railway.app`.

### B4 — Deploy the Frontend

1. In your Railway project, click **New Service** → **GitHub Repo** → same repo
2. Under **Settings**:
   - **Root Directory:** `frontend`
   - **Build Command:** `npm install && npm run build`
   - **Start Command:** leave blank (it's static files)
3. Add one **Variable:**

| Variable | Value |
|----------|-------|
| `VITE_API_URL` | `https://your-backend-url.railway.app/api` (from step B3) |

4. Generate a domain for the frontend too (Settings → Networking)
5. Go back to the **backend** service and update `FRONTEND_URL` to the frontend's Railway domain

### B5 — Set Up the Database Tables

After the backend deploys successfully, go to the backend service in Railway, click **Settings** → find the **Deploy** section, and look for a way to run a one-time command. Or open a terminal in Railway:

```
alembic upgrade head
```

If you can't find this option, the app will auto-create tables on first startup (it has a fallback).

---

## Using the App

Once running (either option), visit the URL in your browser:

1. **Log in** with your `APP_USERNAME` and `APP_PASSWORD`
2. **Add a tracking number:** Click "Add Tracking", enter the number and select the carrier, give it a nickname (e.g. "Table order from supplier")
3. **View status:** The dashboard shows all your shipments with current status, location, and estimated delivery
4. **Refresh:** The app automatically checks for updates every 6 hours. You can also click the refresh button manually.
5. **Event history:** Click on any shipment to see the full history of scans and locations

---

## Supported Carriers

| Carrier | Works Locally | Works on Cloud | Notes |
|---------|:---:|:---:|-------|
| Day & Ross | ✅ | ✅ | Full support |
| Polaris Transport | ✅ | ✅ | Full support |
| UPS | ✅ | ⚠️ | Cloud IPs blocked by Akamai security |
| FedEx | ✅ | ⚠️ | Cloud IPs blocked by Akamai security |

---

## Troubleshooting

**"pip is not recognized" error**
> Try `python -m pip install -r requirements.txt` instead of `pip install ...`

**"python is not recognized" error**
> Python wasn't added to PATH during install. Uninstall Python and reinstall it, making sure to tick "Add Python to PATH" on the first screen.

**Backend starts but shows database errors**
> Double-check your `DATABASE_URL` in the `.env` file. Make sure you copied the full Neon connection string including `?sslmode=require` at the end. Run `alembic upgrade head` again.

**The app loads but tracking returns errors for UPS/FedEx**
> This is expected on cloud hosting. UPS and FedEx block automated requests from cloud server IPs. Run the app locally (Option A) for full UPS/FedEx support.

**Cloudflare tunnel URL changes every restart**
> The quick tunnel (`cloudflared tunnel --url ...`) gives a different URL each time. For a permanent URL, set up a named tunnel with a Cloudflare account (free) as described in step A3.

**Page loads but shows "Network Error" or "Cannot connect"**
> The backend is not running. Make sure the `uvicorn` command (Step A1) is still running in its Command Prompt window.

---

## Updating the App

When there is a new version of the code:

```
git pull origin master
cd backend
pip install -r requirements.txt
alembic upgrade head
cd ..
```

Then restart the backend (stop the `uvicorn` window and run the command again).

For Railway/cloud: just push to GitHub and Railway will automatically redeploy.

---

## Technical Overview (for IT staff)

- **Backend:** Python 3.12 + FastAPI + SQLAlchemy + Alembic
- **Frontend:** React + Vite + TailwindCSS
- **Database:** PostgreSQL (Neon.tech free tier recommended)
- **Scraping:** Microsoft Playwright (Chromium headless for Day & Ross/Polaris; non-headless Chrome via Xvfb on Linux for UPS/FedEx)
- **Auth:** Single shared-user JWT login, configurable via env vars
- **Scheduler:** APScheduler refreshes all active shipments every 6 hours
- **Docker:** Backend ships as a Docker image (see `backend/Dockerfile`); includes Chromium + Chrome for Testing + Xvfb dependencies

Environment variables required:
```
DATABASE_URL        — PostgreSQL connection string
SECRET_KEY          — JWT signing key (any long random string)
APP_USERNAME        — Shared login username
APP_PASSWORD        — Shared login password
FRONTEND_URL        — Frontend origin for CORS (e.g. https://yourapp.com)
```
