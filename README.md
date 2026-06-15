# Website Monitor
 
Automatically checks a website for changes every 30 minutes and sends an email alert if anything changes. Runs for free on GitHub Actions — no server or scheduler needed.
 
## How it works
 
1. GitHub Actions runs `monitor.py` on a schedule
2. The script fetches the target page and hashes its content
3. If the hash differs from the last saved one, an alert email is sent
4. The new hash is committed back to the repo in `state.json` for the next run
## Setup
 
### 1. Configure the URL
 
In `monitor.py`, change line 16 to the site you want to watch:
 
```python
URL_TO_WATCH = "https://yoursite.com"
```
 
### 2. Add GitHub Secrets
 
Go to your repo → **Settings → Secrets and variables → Actions** and add:
 
| Secret name | Value |
|---|---|
| `EMAIL_SENDER` | Your Gmail address |
| `EMAIL_PASSWORD` | Your Gmail [App Password](https://myaccount.google.com/apppasswords) |
| `EMAIL_RECIPIENT` | Where alerts should be sent |
 
> **Note:** Use a Gmail App Password, not your regular Gmail login password. Generate one at myaccount.google.com/apppasswords.
 
### 3. Push to GitHub
 
```bash
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/website-monitor.git
git push -u origin main
```
 
### 4. Test it
 
Go to the **Actions** tab in your repo → select **Website Monitor** → click **Run workflow**. This triggers an immediate run so you can verify the email works.
 
## File structure
 
```
your-repo/
├── monitor.py                      # the monitor script
├── state.json                      # auto-generated; stores the last known hash
├── .gitignore
└── .github/
    └── workflows/
        └── monitor.yml             # GitHub Actions schedule and job config
```
 
## Changing the check frequency
 
Edit the cron expression in `.github/workflows/monitor.yml`:
 
```yaml
- cron: '*/30 * * * *'   # every 30 minutes
- cron: '0 * * * *'      # every hour
- cron: '0 9 * * *'      # once a day at 9am UTC
```
 
> GitHub Actions does not guarantee exact timing for scheduled workflows — runs may be delayed by a few minutes during high-traffic periods.
 
