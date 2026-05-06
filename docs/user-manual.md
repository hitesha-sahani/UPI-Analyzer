# Clarity Money OS - User Manual

## 1. What Clarity Money OS Is

Clarity Money OS is a personal finance assistant that turns your UPI, wallet, bank, and PhonePe statement data into a clear picture of how your money moves.

It is built for people who want to understand their everyday spending without maintaining spreadsheets. You upload your transaction history, and the app cleans it, categorizes it, detects duplicate entries, finds unusual transactions, highlights recurring charges, estimates savings, and turns your behavior into plain-language insights.

The app is designed around one simple idea:

> Know your money. Fix the leaks.

## 2. Who It Is For

Clarity Money OS is useful for:

- Students tracking food, shopping, subscriptions, and transfers
- Working professionals reviewing salary, UPI spends, BNPL, and card payments
- Families trying to understand monthly expenses
- Anyone with multiple UPI apps or bank exports
- Users who want financial coaching based on real transaction data
- Demo users who want a clear personal finance story from sample data

## 3. What The App Can Do

Clarity Money OS helps you:

- Upload CSV statements or PhonePe PDF statements
- Merge multiple account exports
- Detect and review duplicate transactions
- Categorize merchants automatically
- Manually correct merchant categories
- Calculate spend, income, savings, daily burn, and savings rate
- Find silent leaks such as subscriptions, food delivery drift, BNPL pressure, and unusual payments
- Track budgets by category and month
- Review all transactions with filters and search
- Learn from your own spending habits
- Ask an AI coach questions about your money
- View a narrative financial timeline month by month

## 4. Supported Inputs

### CSV files

The app accepts CSV files from UPI apps, wallets, and bank exports when they contain recognizable transaction columns.

Minimum recommended columns:

- `Date`
- `Amount`
- `Description`
- `Type` or `DR/CR`

Optional but useful columns:

- `UPI ID`
- `VPA`
- `Balance`
- `Txn ID`
- `Reference`
- `Chq/Ref No`

### PhonePe PDF statements

The app also supports PhonePe statement PDFs when the text can be extracted. Scanned image-only PDFs may fail unless the text is readable.

### Demo files

The repo includes sample files in `data/`, including:

- `sample_transactions.csv`
- `demo_same_account_export_a.csv`
- `demo_same_account_export_b.csv`

The two demo same-account exports are useful for showcasing duplicate detection across uploaded files.

## 5. Installation

### Requirements

Install:

- Python 3.10 or newer
- pip
- A modern browser

### Setup steps

1. Open a terminal in the project folder.
2. Create a virtual environment:

```bash
python -m venv venv
```

3. Activate the environment:

```bash
# Windows
venv\Scripts\activate
```

```bash
# macOS / Linux
source venv/bin/activate
```

4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Optional: configure the AI Coach.

The AI Coach uses Groq if available. Set either a Streamlit secret or an environment variable:

```env
GROQ_API_KEY=your_groq_api_key
```

6. Start the app:

```bash
streamlit run app.py
```

7. Open the local URL shown by Streamlit, usually:

```text
http://localhost:8501
```

## 6. First-Time Use

When the app opens, you will see the Clarity landing page.

You can either:

- upload your own primary CSV or PhonePe PDF
- add optional extra accounts or exports
- use the built-in demo data

Recommended first demo:

1. Upload `data/demo_same_account_export_a.csv` as the primary file.
2. Upload `data/demo_same_account_export_b.csv` under `Add more accounts`.
3. Let the app process the files.
4. Review merchant categories when prompted.
5. Open the Duplicate Review page.
6. Continue to Dashboard, Timeline, Leaks, Budget, Transactions, Merchants, Learn, and AI Coach.

## 7. Main Workflow

### Step 1: Upload your data

Use the upload panel to select your primary statement file. You can add more files if you use multiple accounts or multiple UPI apps.

The app reads the files, normalizes column names, parses dates and amounts, and prepares a clean transaction table.

### Step 2: Review merchants

After upload, the app may ask you to review merchant categories.

This step improves accuracy because local payees, transfers, and unclear UPI descriptions can be hard to auto-classify.

You can:

- search for a payee
- change its category
- save rules for future uploads

### Step 3: Review duplicates

If more than one account/export was uploaded, the sidebar shows `Duplicate Review`.

The app flags possible duplicates across different sources using:

- exact reference matches
- exact transaction ID matches
- timestamp and amount matches
- fuzzy description matching
- merchant and amount matching

You decide whether each candidate should be removed or kept.

### Step 4: Explore insights

Use the sidebar pages to inspect your financial story.

## 8. Page Guide

### Dashboard

The Dashboard is the command center.

It shows:

- Money wellness score
- Best next action
- Total spend
- Estimated savings
- Savings rate
- Top spend area
- Silent leak signals
- Risk checks
- Money story
- Top merchants
- Spend split
- Recent transaction trail
- Learning cards

Example:

If food delivery is unusually high, the dashboard may show food as your top spend area and recommend a weekly cap.

### Timeline

The Timeline turns transaction history into a monthly financial memory.

It shows:

- monthly spend
- savings estimate
- top category
- biggest merchant
- unusual spend
- money score
- month-over-month changes
- recurring subscription notes
- behavioral signals such as weekend spend, payday bursts, and binge days

Use this page when you want to understand how your habits changed over time.

### Learn

The Learn page converts your data into practical financial lessons.

It explains:

- your money personality
- why your top categories matter
- daily burn rate
- repeat habits
- first lever to pull

This page is useful when you want education instead of just numbers.

### Leaks

The Leaks page highlights money drains.

It can surface:

- subscription audit opportunities
- food delivery drift
- BNPL or credit pressure
- large unusual payments

It also lists detected recurring payments with monthly and annual projections.

### Transactions

The Transactions page is the detailed ledger.

You can filter by:

- category
- type
- merchant or description search

Each transaction shows:

- date
- description
- merchant
- category
- amount
- debit or credit
- anomaly signal

### Budget

The Budget page lets you compare real spending against category budgets.

You can:

- set a total monthly spending budget
- view month-by-month budget usage
- select a month
- inspect category progress
- see projected month-end spend
- edit category budgets
- view alerts for over-budget or soon-to-breach categories

Budget status labels include:

- Healthy
- On Track
- Warning
- Over Budget

### Merchants

The Merchants page lets you correct categories.

The app groups payees by UPI description and frequency. You can choose the correct category and save rules.

Saved rules are stored per user and reused on future uploads.

### AI Coach

The AI Coach answers questions using your actual financial context.

Example questions:

- Where is my money leaking?
- What should I cut this month?
- Am I saving enough?
- Which subscriptions can I cancel?
- How impulsive is my spending?
- What is my biggest financial risk?
- Give me a 30-day savings challenge.

The AI Coach requires Groq SDK support and a configured `GROQ_API_KEY`.

### Duplicate Review

This page appears when multiple sources are uploaded.

It shows:

- accounts merged
- total transactions
- flagged duplicate candidates
- confirmed removed amount
- duplicate reasons
- original and flagged transaction pairs

Choose `Remove duplicate` only when the flagged row is truly duplicated. Choose `Keep both` when two similar transactions are legitimate.

## 9. Understanding Key Metrics

### Money wellness score

The score is a local heuristic based on:

- savings rate
- recurring subscription load
- BNPL spend
- food spend share
- high-severity anomaly count

It is not a credit score. It is a spending-health indicator for personal reflection.

### Savings estimate

Savings estimate is:

```text
total credits - total debits
```

If your statement does not include salary or income credits, savings estimate may be incomplete.

### Daily burn

Daily burn estimates average debit spend per day across the uploaded period.

### Silent leaks

Silent leaks are repeated or behavior-driven expenses that may not look dramatic one by one but add up over time.

### Anomalies

Anomalies are transactions flagged by local rules such as:

- unusually large amount
- outlier within a category
- suspicious large round amount
- new merchant with large amount
- high activity day
- possible duplicate charge
- late-night transaction as informational context

## 10. Troubleshooting

### Upload fails or gives no data

Check:

- The file is a CSV or supported PhonePe PDF.
- The file has date and amount columns.
- The CSV is not empty.
- The statement is not password-protected.

Quick fix:

Open the CSV in Excel or Google Sheets and rename columns to:

```text
Date, Description, Amount, Type, UPI_ID, Balance
```

### Debit and credit are wrong

Make sure the file includes one of:

- `Type`
- `DR/CR`
- `Debit/Credit`
- separate `Debit Amount` and `Credit Amount` columns
- signed amounts where debits are negative

### PhonePe PDF does not parse

The PhonePe parser expects text-based statements. If the PDF is scanned or image-only, text extraction may fail.

Try exporting a fresh statement directly from PhonePe.

### AI Coach does not open

Check:

- `groq` is installed from `requirements.txt`
- `GROQ_API_KEY` is set in environment variables or Streamlit secrets
- internet access is available

### Duplicate Review does not appear

Duplicate Review only appears when more than one source is uploaded.

Upload a primary file and at least one additional file under `Add more accounts`.

### Categories look wrong

Use the Merchants page to correct category rules. Saved rules are applied to future uploads.

### Savings rate looks strange

Savings rate depends on income credits being present in the uploaded statement. If the file only contains spending, the savings rate will not represent your full financial picture.

## 11. Privacy Notes

Clarity Money OS works on uploaded transaction data. Treat statements as sensitive.

Recommended practices:

- run locally for personal demos
- avoid sharing real statements publicly
- use demo CSVs for presentations
- remove secrets from `.streamlit/secrets.toml` before sharing code
- do not commit personal bank statements

## 12. FAQ

### Is this a banking app?

No. It does not connect to your bank account. It analyzes uploaded statements.

### Does it move money?

No. It is read-only analytics and coaching.

### Is it financial advice?

No. It provides educational insights and habit signals based on transaction data.

### Can it handle multiple accounts?

Yes. Upload a primary file and optional extra files. The app merges them and flags likely duplicates.

### Can I correct categories?

Yes. Use the Merchants page to save category rules.

### Can I use it without AI?

Yes. Most analytics run locally with pandas and heuristics. Only the AI Coach requires Groq.

### Can I use demo data?

Yes. Use the built-in sample data or the demo CSVs in `data/`.

## 13. Support Checklist

When reporting an issue, include:

- file type
- column names
- screenshot of the error
- whether you uploaded one or multiple files
- whether the AI Coach or local analytics failed
- steps to reproduce

