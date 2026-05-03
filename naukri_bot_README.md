# Naukri Auto-Apply Bot — Fixed Version

## Bug Fixes

### 1. Company Name "N/A" Fix

**Old problem:** Naukri updated its HTML structure in 2024.
The `.comp-name` selector stopped working on some pages.

**Fix applied — 4 layers:**

- **Layer 1:** Try 15+ CSS selectors (`.comp-name`, `[class*='compName']`, `[class*='company-name']`, etc.)
- **Layer 2:** XPath broad search — elements whose class contains `comp`, `company`, or `employer`
- **Layer 3:** Search anchor `aria-label` / `title` attributes for company-related keywords
- **Layer 4:** Also extract company name from the apply page (parsed from the page title)

---

### 2. "Applied by" Name

Change the variable at the top of `main.py`:

```python
APPLICANT_NAME = "Soniya Chowdhary"   # ← Put your name here
```

It will appear in the report like this:

```
Naukri Auto-Apply Report
Applied by: Soniya Chowdhary
Generated: 02 May 2026, 11:39 AM
```

---

## 📁 File Structure

```
naukri_bot/
├── main.py              ← Main bot (run this file)
├── naukri_scraper.py    ← Job scraper (can also be run standalone)
├── job_applier.py       ← Application logic
├── utils/
│   ├── __init__.py
│   └── logger.py        ← Colored logging utility
├── downloads/           ← Resume PDF gets saved here
├── reports/             ← HTML + CSV reports are saved here
└── logs/                ← Log files
```

---

## 🚀 Setup & Run

### Step 1: Install Dependencies

```bash
pip install selenium webdriver-manager pdfplumber
```

### Step 2: Set Your Name

Open `main.py` and update line 30:

```python
APPLICANT_NAME = "Your Name Here"
```

### Step 3: Run the Bot

```bash
python main.py
```

### Step 4: Log In

- A browser window will open automatically
- Log in to your Naukri account
- Press **ENTER** in the terminal to continue

---

## 🔍 Testing the Scraper Only

To test just the scraper without applying to jobs:

```bash
python naukri_scraper.py
```

**Output files generated:**
- `jobs_output.csv`
- `jobs_output.json`

You can verify company names directly in the terminal:

```
→ Python Developer | Company: TCS       | Hyderabad
→ Full Stack Dev   | Company: Infosys   | Delhi
```

---

## ⚠️ If Company Name Shows "N/A"

If Naukri updates its HTML again, the existing selectors may break.
Use Browser DevTools (F12) to find the correct selector manually:

```
1. Press F12 to open DevTools → go to the Inspector / Elements tab
2. Right-click on the company name on the page → click "Inspect"
3. Note the class name shown in the HTML
4. Add that class name to the CSS_SELECTORS list in naukri_scraper.py
```

---

## 📊 Report Files

| File | Description |
|------|-------------|
| `reports/naukri_report_TIMESTAMP.html` | Visual dashboard — open in any browser |
| `reports/naukri_report_TIMESTAMP.csv`  | Spreadsheet format — open in Excel or Google Sheets |
| `logs/run_TIMESTAMP.log`              | Detailed debug log for troubleshooting |
