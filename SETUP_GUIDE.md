# Student Management Portal - Setup & Deployment Guide

## Local Development Setup

### 1. Create `.env` file
Copy the `.env.example` file to `.env` and update with your values:
```bash
cp .env.example .env
```

### 2. Update `.env` with your credentials
```
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your_random_secret_key_here
DATABASE_URL=sqlite:///students.db
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_DEFAULT_SENDER=your_email@gmail.com
```

### 3. Install dependencies
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 4. Run locally
```bash
python app.py
# or
flask run
```

---

## Vercel Deployment Setup

### Step 1: Get Gmail App Password
For email functionality, you need a Gmail App Password (NOT your regular password):

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable 2-factor authentication if not already enabled
3. Go to "App passwords"
4. Select "Mail" and "Windows Computer" (or your device)
5. Copy the 16-character password

### Step 2: Set Environment Variables on Vercel

1. **Push your code to GitHub** (required for Vercel)
2. **Go to [Vercel Dashboard](https://vercel.com/dashboard)**
3. **Click on your project** or create new project from GitHub
4. **Go to Settings → Environment Variables**
5. **Add the following variables:**

```
FLASK_APP = app.py
FLASK_ENV = production
SECRET_KEY = (generate a strong random key - at least 32 characters)
DATABASE_URL = (your PostgreSQL database URL from Supabase/Railway/etc)
MAIL_SERVER = smtp.gmail.com
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = your_email@gmail.com
MAIL_PASSWORD = (paste the 16-character Gmail App Password here)
MAIL_DEFAULT_SENDER = your_email@gmail.com
```

### Step 3: Important Configuration

**Create a strong SECRET_KEY:**
```python
import secrets
print(secrets.token_hex(32))
```

**Use a production database** (NOT SQLite):
- Recommended: Supabase PostgreSQL (free tier available)
- Or: Railway, Heroku Postgres, etc.

### Step 4: Update Redirect URLs

If your app is running on `https://your-app.vercel.app`:
1. Update any hardcoded URLs in templates (if any)
2. Check that all redirects use `url_for()` function
3. The ProxyFix middleware in app.py handles HTTPS redirects automatically ✅

---

## Troubleshooting Redirects

### ✅ Correct redirect usage (WORKING):
```python
return redirect(url_for('auth.login'))
return redirect(url_for('students.view', student_id=user.student_id))
```

### ❌ Incorrect redirect usage (BROKEN):
```python
return redirect('/login')  # Don't use hardcoded paths
return redirect('http://localhost:5000/login')  # Don't use full URLs
```

---

## Environment Variables Explained

| Variable | Purpose | Example |
|----------|---------|---------|
| `FLASK_APP` | Flask entry point | app.py |
| `FLASK_ENV` | Development or production | development / production |
| `SECRET_KEY` | Session encryption key | 32+ random characters |
| `DATABASE_URL` | Database connection | postgresql://user:pass@host/db |
| `MAIL_USERNAME` | Gmail account for sending emails | your_email@gmail.com |
| `MAIL_PASSWORD` | Gmail App Password (NOT regular password) | 16-character code from Google |
| `MAIL_DEFAULT_SENDER` | Sender email address | your_email@gmail.com |

---

## Testing

### Local:
```bash
python app.py
# Visit http://localhost:5000
```

### After Vercel Deploy:
1. Check your deployed URL
2. Test login redirect
3. Test dashboard/students redirects
4. Check email functionality (if configured)

---

## Common Issues & Fixes

### ❌ "Module not found" error
**Fix:** Make sure `requirements.txt` has all dependencies and you've installed them

### ❌ Redirects going to wrong URL
**Fix:** Always use `url_for()` function instead of hardcoded paths

### ❌ Email not sending
**Fix:** 
- Verify Gmail App Password is correct
- Check MAIL_USERNAME matches the account
- Ensure 2FA is enabled on Gmail

### ❌ Sessions not persisting on Vercel
**Fix:** Already handled with ProxyFix and SESSION_COOKIE_SECURE settings ✅

---

## API Keys Summary

Currently configured for:
- ✅ **Gmail SMTP** (for sending emails)
- ✅ **Flask Session Management** (built-in)

Future additions (if needed):
- SMS API (Twilio, etc.)
- Cloud Storage (AWS S3, etc.)
- Third-party auth (Google OAuth, etc.)

---

For questions or issues, check the environment variables are correctly set!
