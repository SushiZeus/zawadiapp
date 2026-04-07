# 🍽️ Zawadi's Kitchenwares & More — Business Management System

A Streamlit web app for managing inventory, sales, purchases, and expenses for Zawadi's Kitchenwares.

## Features
- 📦 **Inventory Tracker** — View all stock, low-stock alerts, adjust quantities
- 🛒 **Purchases Ledger** — All stock purchases from Excel (dozen & single items)
- 💰 **Sales Ledger** — Record daily sales (½ dozen, 1 dozen, or single units)
- 💸 **Expenses** — Track business expenses (rent, transport, electricity, etc.)
- 📊 **Profit & Summary** — Net profit, gross profit, breakdown by item & category
- 🏠 **Dashboard** — Overview of key metrics and low-stock alerts

## Currency
All amounts displayed in **Tanzanian Shillings (TZS)**

---

## 🚀 Deploy on Streamlit Cloud (Free)

### Step 1 — Push to GitHub
1. Create a **new repository** on [github.com](https://github.com) (e.g. `zawadiapp`)
2. Upload ALL files from this folder:
   - `app.py`
   - `requirements.txt`
   - `Zawadi’s Kitchenwares.xlsx`
   - `.gitignore`
   - `README.md`

   Or use Git:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/zawadiapp.git
   git push -u origin main
   ```

### Step 2 — Deploy on Streamlit Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with your GitHub account
3. Click **"New app"**
4. Select your repository (`zawadiapp`), branch (`main`), and main file (`app.py`)
5. Click **"Deploy"** — your app will be live in ~2 minutes!

### Step 3 — Your app URL
You'll get a free URL like:
```
https://zawadiapp-yourname.streamlit.app
```

---

## 📁 File Structure
```
zawadi_app/
├── app.py                          # Main Streamlit app
├── requirements.txt                # Python dependencies
├── Zawadi’s Kitchenwares.xlsx      # Your product master data
├── .gitignore                      # Excludes local data files
└── README.md                       # This file
```

> **Note:** Sales, expenses, and inventory adjustments are saved in a `data/` folder locally. On Streamlit Cloud, data resets when the app restarts. For permanent storage, consider upgrading to a database (ask Claude to add SQLite support).

---

## 💡 How to Use

### Recording a Sale
1. Go to **Sales Ledger**
2. Select the item, selling mode (½ doz / 1 doz / single), and quantity
3. Price is auto-filled from your master data — edit if needed
4. Click **Record Sale** — stock is automatically reduced

### Adding an Expense
1. Go to **Expenses**
2. Select category (Rent, Transport, Electricity, etc.)
3. Enter amount and description
4. Click **Save Expense**

### Checking Profit
1. Go to **Profit & Summary**
2. See gross profit, expenses, and net profit
3. View breakdown by item and expense category

---

Built with ❤️ using [Streamlit](https://streamlit.io)
