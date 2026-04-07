import streamlit as st
import pandas as pd
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
import calendar

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Zawadi's Kitchenwares",
    page_icon="🍽️",
    layout="wide",
)

# ── Persistent storage (JSON files) ──────────────────────────────────────────
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

SALES_FILE = DATA_DIR / "sales.json"
EXPENSES_FILE = DATA_DIR / "expenses.json"
INVENTORY_FILE = DATA_DIR / "inventory.json"

def load_json(path, default):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)

# ── Helper Functions ──────────────────────────────────────────────────────────
def fmt(n):
    """Format number as TZS currency with 2 decimal places and commas"""
    try:
        if pd.isna(n) or n is None:
            return "TZS 0.00"
        return f"TZS {float(n)::,.2f}"
    except (ValueError, TypeError):
        return str(n)

def fmt_price_only(n):
    """Format price only (without TZS prefix) with commas and 2 decimals"""
    try:
        if pd.isna(n) or n is None:
            return "0.00"
        return f"{float(n)::,.2f}"
    except (ValueError, TypeError):
        return str(n)

def safe_float(value, default=0):
    """Safely convert to float, handling NaN, None, and Series"""
    try:
        if hasattr(value, 'iloc'):
            value = value.iloc[0] if len(value) > 0 else default
        if pd.isna(value) or value is None:
            return default
        if isinstance(value, str):
            value = value.replace(',', '').strip()
            if value == '' or value == '-':
                return default
        return float(value)
    except (ValueError, TypeError, AttributeError):
        return default

def safe_int(value, default=0):
    """Safely convert to int, handling NaN and None"""
    try:
        if pd.isna(value) or value is None:
            return default
        return int(float(value))
    except (ValueError, TypeError):
        return default

def get_records_by_date(records, target_date):
    """Filter records by specific date"""
    if not records:
        return []
    return [r for r in records if r.get("date", "") == str(target_date)]

def get_records_by_month(records, year, month):
    """Filter records by month/year"""
    if not records:
        return []
    result = []
    for r in records:
        try:
            record_date = datetime.strptime(r.get("date", ""), "%Y-%m-%d").date()
            if record_date.year == year and record_date.month == month:
                result.append(r)
        except:
            continue
    return result

def get_records_by_date_range(records, start_date, end_date):
    """Filter records by date range"""
    if not records:
        return []
    result = []
    for r in records:
        try:
            record_date = datetime.strptime(r.get("date", ""), "%Y-%m-%d").date()
            if start_date <= record_date <= end_date:
                result.append(r)
        except:
            continue
    return result

# ── Load Excel master data ────────────────────────────────────────────────────
@st.cache_data
def load_master_data():
    # Try different filename variations
    possible_filenames = [
        "Zawadi’s Kitchenwares.xlsx",
        "Zawadi_s_Kitchenwares.xlsx",
        "Zawadi's Kitchenwares.xlsx",
        "Zawadis_Kitchenwares.xlsx"
    ]
    
    excel_file = None
    for filename in possible_filenames:
        if os.path.exists(filename):
            excel_file = filename
            break
    
    if excel_file is None:
        st.error("❌ Could not find the Excel data file. Please ensure the Excel file is in the app directory.")
        st.stop()
    
    try:
        xl = pd.read_excel(excel_file, sheet_name=None)
        
        if "Master" not in xl:
            st.error("❌ Sheet 'Master' not found in the Excel file")
            st.stop()
        if "Single Master" not in xl:
            st.error("❌ Sheet 'Single Master' not found in the Excel file")
            st.stop()
        
        master = xl["Master"].copy()
        master = master[master["ITEM"].notna()]
        master = master[master["ITEM"].astype(str).str.strip() != ""]
        master = master[master["ITEM"].astype(str).str.strip() != "nan"]
        master = master.reset_index(drop=True)
        
        single = xl["Single Master"].copy()
        single = single[single["ITEM"].notna()]
        single = single[single["ITEM"].astype(str).str.strip() != ""]
        single = single[single["ITEM"].astype(str).str.strip() != "nan"]
        single = single.reset_index(drop=True)
        
        master["DATE"] = master["DATE"].ffill()
        master["VENDOR"] = master["VENDOR"].ffill()
        single["DATE"] = single["DATE"].ffill()
        single["VENDOR"] = single["VENDOR"].ffill()
        
        return master, single
    
    except Exception as e:
        st.error(f"❌ Error reading Excel file: {str(e)}")
        st.stop()

# Load the data
master_df, single_df = load_master_data()

# ── Build inventory from Excel + saved overrides ──────────────────────────────
@st.cache_data(ttl=60)
def build_inventory():
    saved = load_json(INVENTORY_FILE, {})
    rows = []
    
    for _, r in master_df.iterrows():
        name = str(r["ITEM"]).strip()
        if not name or name == "nan":
            continue
            
        cartons = safe_float(r.get("CTN(S)", 0))
        pcs_per_carton = safe_float(r.get("PCS/CARTON", 0))
        total_pcs = safe_int(cartons * pcs_per_carton)
        
        # CRITICAL CHANGE: Stock Remaining determines Total Pcs
        stock = saved.get(name, {}).get("stock", total_pcs)
        threshold = saved.get(name, {}).get("threshold", 12)
        
        # Total Pcs now equals Stock Remaining (not the original calculation)
        total_pcs = stock  # <-- CHANGE HERE: Total Pcs follows Stock Remaining
        
        buy_price = safe_float(r.get("BUYING PRICE/CARTON", 0))
        sell_half_doz = safe_float(r.get("1/2 Doz S.P", 0))
        sell_one_doz = safe_float(r.get("1 Doz S.P", 0))
        profit_doz = safe_float(r.get("PROFIT/Doz", 0))
        
        rows.append({
            "Item": name, "Type": "Dozen",
            "Vendor": str(r.get("VENDOR", "")) if pd.notna(r.get("VENDOR")) else "",
            "Cartons": cartons, "Pcs/Carton": pcs_per_carton,
            "Total Pcs": total_pcs, "Stock Remaining": stock,
            "Buy Price/Carton (TZS)": buy_price,
            "Sell ½ Doz (TZS)": sell_half_doz,
            "Sell 1 Doz (TZS)": sell_one_doz,
            "Profit/Doz (TZS)": profit_doz,
            "Low Stock Threshold": threshold,
        })
    
    for _, r in single_df.iterrows():
        name = str(r["ITEM"]).strip()
        if not name or name == "nan":
            continue
            
        cartons = safe_float(r.get("CTN(S)", 0))
        pcs_per_carton = safe_float(r.get("PCS/CARTON", 0))
        total_pcs = safe_int(cartons * pcs_per_carton)
        
        # CRITICAL CHANGE: Stock Remaining determines Total Pcs
        stock = saved.get(name, {}).get("stock", total_pcs)
        threshold = saved.get(name, {}).get("threshold", 5)
        
        # Total Pcs now equals Stock Remaining
        total_pcs = stock  # <-- CHANGE HERE: Total Pcs follows Stock Remaining
        
        buy_price = safe_float(r.get("BUYING PRICE/CARTON", 0))
        sell_price_unit = safe_float(r.get("1 Item S.Price", 0))
        profit_unit = safe_float(r.get("PROFIT/Unit", 0))
        
        rows.append({
            "Item": name, "Type": "Single",
            "Vendor": str(r.get("VENDOR", "")) if pd.notna(r.get("VENDOR")) else "",
            "Cartons": cartons, "Pcs/Carton": pcs_per_carton,
            "Total Pcs": total_pcs, "Stock Remaining": stock,
            "Buy Price/Carton (TZS)": buy_price,
            "Sell ½ Doz (TZS)": "-",
            "Sell 1 Doz (TZS)": "-",
            "Sell Price/Unit (TZS)": sell_price_unit,
            "Profit/Unit (TZS)": profit_unit,
            "Low Stock Threshold": threshold,
        })
    
    return rows

def update_stock(item_name, qty_sold):
    saved = load_json(INVENTORY_FILE, {})
    inv = build_inventory()
    item = next((i for i in inv if i["Item"] == item_name), None)
    if not item:
        return
    current = saved.get(item_name, {}).get("stock", item["Total Pcs"])
    threshold = saved.get(item_name, {}).get("threshold", item["Low Stock Threshold"])
    saved[item_name] = {"stock": max(0, current - qty_sold), "threshold": threshold}
    save_json(INVENTORY_FILE, saved)
    st.cache_data.clear()

def delete_sale_by_index(index):
    sales = load_json(SALES_FILE, [])
    if 0 <= index < len(sales):
        deleted = sales.pop(index)
        save_json(SALES_FILE, sales)
        return deleted
    return None

def delete_expense_by_index(index):
    expenses = load_json(EXPENSES_FILE, [])
    if 0 <= index < len(expenses):
        deleted = expenses.pop(index)
        save_json(EXPENSES_FILE, expenses)
        return deleted
    return None

def update_sale(index, updated_sale):
    sales = load_json(SALES_FILE, [])
    if 0 <= index < len(sales):
        sales[index] = updated_sale
        save_json(SALES_FILE, sales)
        return True
    return False

def update_expense(index, updated_expense):
    expenses = load_json(EXPENSES_FILE, [])
    if 0 <= index < len(expenses):
        expenses[index] = updated_expense
        save_json(EXPENSES_FILE, expenses)
        return True
    return False

def delete_all_sales():
    save_json(SALES_FILE, [])
    return True

def delete_all_expenses():
    save_json(EXPENSES_FILE, [])
    return True

def delete_all_inventory_overrides():
    save_json(INVENTORY_FILE, {})
    st.cache_data.clear()
    return True

# ── Sidebar navigation ────────────────────────────────────────────────────────
st.sidebar.image("https://em-content.zobj.net/source/twitter/376/fork-and-knife-with-plate_1f37d-fe0f.png", width=60)
st.sidebar.title("Zawadi's Kitchenwares")
st.sidebar.caption("Business Management System")

page = st.sidebar.radio(
    "Navigate",
    ["🏠 Dashboard", "📦 Inventory", "🛒 Purchases Ledger",
     "💰 Sales Ledger", "💸 Expenses", "📊 Profit & Summary",
     "🗓️ Calendar View", "⚙️ Data Management"],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.caption(f"Today: {date.today().strftime('%d %b %Y')}")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if page == "🏠 Dashboard":
    st.title("🏠 Dashboard — Zawadi's Kitchenwares & More")
    st.markdown("---")

    inv = build_inventory()
    sales = load_json(SALES_FILE, [])
    expenses = load_json(EXPENSES_FILE, [])

    sales_df = pd.DataFrame(sales) if sales else pd.DataFrame()
    expenses_df = pd.DataFrame(expenses) if expenses else pd.DataFrame()

    total_sales = sales_df["total_price"].astype(float).sum() if not sales_df.empty else 0
    total_profit = sales_df["profit"].astype(float).sum() if not sales_df.empty else 0
    total_expenses = expenses_df["amount"].astype(float).sum() if not expenses_df.empty else 0
    net_profit = total_profit - total_expenses

    low_stock_items = [i for i in inv if i["Stock Remaining"] <= i["Low Stock Threshold"]]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Sales Revenue", fmt(total_sales))
    c2.metric("Gross Profit", fmt(total_profit))
    c3.metric("Total Expenses", fmt(total_expenses))
    c4.metric("Net Profit", fmt(net_profit))

    st.markdown("---")

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("⚠️ Low Stock Alerts")
        if low_stock_items:
            for item in low_stock_items[:10]:
                st.error(f"**{item['Item']}** — {item['Stock Remaining']} pcs left (threshold: {item['Low Stock Threshold']})")
        else:
            st.success("All items are sufficiently stocked ✅")

    with col_b:
        st.subheader("🕐 Recent Sales")
        if not sales_df.empty:
            recent = sales_df.tail(5)[["date", "item", "qty_label", "total_price", "profit"]].copy()
            recent.columns = ["Date", "Item", "Qty", "Revenue (TZS)", "Profit (TZS)"]
            st.dataframe(recent, use_container_width=True, hide_index=True)
        else:
            st.info("No sales recorded yet.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: INVENTORY
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📦 Inventory":
    st.title("📦 Inventory")
    st.markdown("---")

    inv = build_inventory()
    saved = load_json(INVENTORY_FILE, {})

    tab1, tab2, tab3 = st.tabs(["📋 All Stock", "⚠️ Low Stock", "✏️ Adjust Stock"])

    with tab1:
        filter_type = st.selectbox("Filter by type", ["All", "Dozen", "Single"], key="filter_type")
        search = st.text_input("Search item name", key="search_item")
        df = pd.DataFrame(inv)
        if filter_type != "All":
            df = df[df["Type"] == filter_type]
        if search:
            df = df[df["Item"].str.contains(search, case=False)]

        def highlight_low(row):
            color = "background-color: #ffe6e6" if row["Stock Remaining"] <= row["Low Stock Threshold"] else ""
            return [color] * len(row)

        display_cols = ["Item", "Type", "Vendor", "Total Pcs", "Stock Remaining",
                        "Low Stock Threshold", "Buy Price/Carton (TZS)"]
        
        # Format the price column for display
        display_df = df[display_cols].copy()
        display_df["Buy Price/Carton (TZS)"] = display_df["Buy Price/Carton (TZS)"].apply(fmt_price_only)
        
        st.dataframe(
            display_df.style.apply(highlight_low, axis=1),
            use_container_width=True, hide_index=True
        )
        st.caption("🔴 Red rows = stock at or below threshold")

    with tab2:
        low = [i for i in inv if i["Stock Remaining"] <= i["Low Stock Threshold"]]
        if low:
            low_df = pd.DataFrame(low)[["Item", "Type", "Vendor", "Stock Remaining", "Low Stock Threshold"]]
            st.dataframe(low_df, use_container_width=True, hide_index=True)
        else:
            st.success("No low stock items right now ✅")

    with tab3:
        st.subheader("Adjust stock or set low-stock threshold")
        item_names = [i["Item"] for i in inv]
        if item_names:
            sel = st.selectbox("Select item", item_names, key="select_item")
            item_data = next(i for i in inv if i["Item"] == sel)

            col1, col2 = st.columns(2)
            with col1:
                new_stock = st.number_input("Set stock remaining (pcs)", min_value=0,
                                            value=int(item_data["Stock Remaining"]), key="new_stock")
            with col2:
                new_thresh = st.number_input("Low stock threshold (pcs)", min_value=1,
                                             value=int(item_data["Low Stock Threshold"]), key="new_thresh")

            if st.button("💾 Save Changes", key="save_inventory_changes"):
                saved[sel] = {"stock": new_stock, "threshold": new_thresh}
                save_json(INVENTORY_FILE, saved)
                st.success(f"Updated **{sel}**: stock={new_stock}, threshold={new_thresh}")
                st.cache_data.clear()
                st.rerun()
        else:
            st.warning("No items found in inventory")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: PURCHASES LEDGER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🛒 Purchases Ledger":
    st.title("🛒 Purchases Ledger")
    st.markdown("---")

    st.subheader("All Purchases (from Excel)")
    tab1, tab2 = st.tabs(["Dozen Items (Master)", "Single Items"])

    with tab1:
        if not master_df.empty:
            disp = master_df[["DATE", "VENDOR", "ITEM", "CTN(S)", "PCS/CARTON",
                              "BUYING PRICE/CARTON", "1 Doz S.P", "PROFIT/Doz", "Profit/Carton"]].copy()
            disp.columns = ["Date", "Vendor", "Item", "Cartons", "Pcs/Carton",
                            "Buy Price/Carton", "Sell 1 Doz", "Profit/Doz", "Profit/Carton"]
            
            # Format prices with commas and 2 decimals
            for col in ["Buy Price/Carton", "Sell 1 Doz", "Profit/Doz", "Profit/Carton"]:
                disp[col] = disp[col].apply(lambda x: fmt_price_only(safe_float(x)) if safe_float(x) > 0 else "-")
            
            st.dataframe(disp, use_container_width=True, hide_index=True)

            total_spent = 0
            for idx, row in master_df.iterrows():
                price = safe_float(row.get("BUYING PRICE/CARTON", 0))
                cartons = safe_float(row.get("CTN(S)", 0))
                total_spent += price * cartons
            
            st.info(f"**Total spent on dozen stock: {fmt(total_spent)}**")
        else:
            st.info("No dozen items found")

    with tab2:
        if not single_df.empty:
            disp2 = single_df[["DATE", "VENDOR", "ITEM", "CTN(S)", "PCS/CARTON",
                               "BUYING PRICE/CARTON", "1 Item S.Price", "PROFIT/Unit", "Profit/Carton"]].copy()
            disp2.columns = ["Date", "Vendor", "Item", "Cartons", "Pcs/Carton",
                             "Buy Price/Carton", "Sell Price/Unit", "Profit/Unit", "Profit/Carton"]
            
            # Format prices with commas and 2 decimals
            for col in ["Buy Price/Carton", "Sell Price/Unit", "Profit/Unit", "Profit/Carton"]:
                disp2[col] = disp2[col].apply(lambda x: fmt_price_only(safe_float(x)) if safe_float(x) > 0 else "-")
            
            st.dataframe(disp2, use_container_width=True, hide_index=True)

            total_spent2 = 0
            for idx, row in single_df.iterrows():
                price = safe_float(row.get("BUYING PRICE/CARTON", 0))
                cartons = safe_float(row.get("CTN(S)", 0))
                total_spent2 += price * cartons
            
            st.info(f"**Total spent on single stock: {fmt(total_spent2)}**")
        else:
            st.info("No single items found")

    grand_total = 0
    for idx, row in master_df.iterrows():
        grand_total += safe_float(row.get("BUYING PRICE/CARTON", 0)) * safe_float(row.get("CTN(S)", 0))
    for idx, row in single_df.iterrows():
        grand_total += safe_float(row.get("BUYING PRICE/CARTON", 0)) * safe_float(row.get("CTN(S)", 0))
    
    st.success(f"### 💰 Grand Total Purchases: {fmt(grand_total)}")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SALES LEDGER (with edit/delete capabilities)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💰 Sales Ledger":
    st.title("💰 Sales Ledger")
    st.markdown("---")

    sales = load_json(SALES_FILE, [])
    inv = build_inventory()

    # ── Record new sale ───────────────────────────────────────────────────────
    with st.expander("➕ Record New Sale", expanded=True):
        with st.form("sale_form"):
            col1, col2, col3 = st.columns(3)

            all_items = [i["Item"] for i in inv]
            with col1:
                sale_date = st.date_input("Date", value=date.today())
                if all_items:
                    item_name = st.selectbox("Item", all_items)
                else:
                    item_name = None
                    st.error("No items available in inventory")

            if item_name:
                item_data = next((i for i in inv if i["Item"] == item_name), None)
                item_type = item_data["Type"] if item_data else "Single"

                with col2:
                    if item_type == "Dozen":
                        sell_mode = st.selectbox("Sell by", ["½ Dozen (6 pcs)", "1 Dozen (12 pcs)"])
                    else:
                        sell_mode = st.selectbox("Sell by", ["Single unit"])
                    quantity = st.number_input("Quantity", min_value=1, value=1)

                with col3:
                    if item_data:
                        if item_type == "Dozen":
                            if "½" in sell_mode:
                                auto_price = safe_float(item_data.get("Sell ½ Doz (TZS)", 0))
                                auto_profit = safe_float(item_data.get("Profit/Doz (TZS)", 0)) / 2
                                pcs_per_unit = 6
                            else:
                                auto_price = safe_float(item_data.get("Sell 1 Doz (TZS)", 0))
                                auto_profit = safe_float(item_data.get("Profit/Doz (TZS)", 0))
                                pcs_per_unit = 12
                        else:
                            auto_price = safe_float(item_data.get("Sell Price/Unit (TZS)", 0))
                            auto_profit = safe_float(item_data.get("Profit/Unit (TZS)", 0))
                            pcs_per_unit = 1
                    else:
                        auto_price, auto_profit, pcs_per_unit = 0, 0, 1

                    unit_price = st.number_input("Selling price per unit (TZS)", min_value=0, value=int(auto_price))
                    unit_profit = st.number_input("Profit per unit (TZS)", min_value=0, value=int(auto_profit))
                    customer = st.text_input("Customer (optional)")

                submitted = st.form_submit_button("💾 Record Sale")
                if submitted and item_name:
                    total_price = unit_price * quantity
                    total_profit = unit_profit * quantity
                    total_pcs = pcs_per_unit * quantity
                    entry = {
                        "date": str(sale_date),
                        "item": item_name,
                        "type": item_type,
                        "sell_mode": sell_mode,
                        "quantity": quantity,
                        "qty_label": f"{quantity} × {sell_mode}",
                        "pcs_sold": total_pcs,
                        "unit_price": unit_price,
                        "total_price": total_price,
                        "unit_profit": unit_profit,
                        "profit": total_profit,
                        "customer": customer,
                    }
                    sales.append(entry)
                    save_json(SALES_FILE, sales)
                    update_stock(item_name, total_pcs)
                    st.success(f"✅ Sale recorded: {item_name} — {fmt(total_price)}")
                    st.rerun()

    st.markdown("---")

    # ── View, Edit, Delete Sales ───────────────────────────────────────────────
    st.subheader("📋 Sales Records")
    
    if sales:
        # Date filters
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            view_option = st.selectbox("View by", ["All Records", "Specific Date", "Date Range", "Month/Year"], key="sales_view_option")
        
        filtered_sales = sales.copy()
        
        if view_option == "Specific Date":
            with col_f2:
                target_date = st.date_input("Select Date", value=date.today(), key="sales_target_date")
            filtered_sales = get_records_by_date(sales, target_date)
        elif view_option == "Date Range":
            with col_f2:
                start_date = st.date_input("Start Date", value=date.today() - timedelta(days=30), key="sales_start_date")
            with col_f3:
                end_date = st.date_input("End Date", value=date.today(), key="sales_end_date")
            filtered_sales = get_records_by_date_range(sales, start_date, end_date)
        elif view_option == "Month/Year":
            with col_f2:
                selected_month = st.selectbox("Month", range(1, 13), index=date.today().month - 1, key="sales_month")
            with col_f3:
                selected_year = st.number_input("Year", min_value=2020, max_value=2030, value=date.today().year, key="sales_year")
            filtered_sales = get_records_by_month(sales, selected_year, selected_month)
        
        if filtered_sales:
            df = pd.DataFrame(filtered_sales)
            df["display_date"] = pd.to_datetime(df["date"]).dt.strftime("%d %b %Y")
            
            # Display with selection for edit/delete
            st.write(f"**Found {len(filtered_sales)} records**")
            
            # Create a selectable table
            for idx, row in df.iterrows():
                with st.container():
                    col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 2, 1, 1])
                    with col1:
                        st.write(row["display_date"])
                    with col2:
                        st.write(row["item"])
                    with col3:
                        st.write(row["qty_label"])
                    with col4:
                        st.write(fmt(row["total_price"]))
                    with col5:
                        if st.button(f"✏️ Edit", key=f"edit_sale_{idx}_{row.get('date', idx)}"):
                            st.session_state.edit_sale_idx = idx
                            st.session_state.edit_sale_data = row.to_dict()
                            st.rerun()
                    with col6:
                        if st.button(f"🗑️ Delete", key=f"del_sale_{idx}_{row.get('date', idx)}"):
                            if delete_sale_by_index(sales.index(row.to_dict())):
                                st.success("Sale deleted successfully!")
                                st.rerun()
                    st.divider()
            
            # Edit form
            if "edit_sale_idx" in st.session_state:
                st.subheader("✏️ Edit Sale Record")
                edit_data = st.session_state.edit_sale_data
                with st.form("edit_sale_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_date = st.date_input("Date", value=datetime.strptime(edit_data["date"], "%Y-%m-%d").date())
                        new_item = st.text_input("Item", value=edit_data["item"])
                        new_quantity = st.number_input("Quantity", value=int(edit_data["quantity"]))
                    with col2:
                        new_unit_price = st.number_input("Unit Price", value=float(edit_data["unit_price"]))
                        new_customer = st.text_input("Customer", value=edit_data.get("customer", ""))
                    
                    if st.form_submit_button("💾 Save Changes"):
                        # Recalculate totals
                        new_total = new_unit_price * new_quantity
                        new_profit = float(edit_data["unit_profit"]) * new_quantity
                        
                        updated_entry = edit_data.copy()
                        updated_entry["date"] = str(new_date)
                        updated_entry["item"] = new_item
                        updated_entry["quantity"] = new_quantity
                        updated_entry["unit_price"] = new_unit_price
                        updated_entry["total_price"] = new_total
                        updated_entry["profit"] = new_profit
                        updated_entry["customer"] = new_customer
                        updated_entry["qty_label"] = f"{new_quantity} × {edit_data['sell_mode']}"
                        
                        original_idx = sales.index(edit_data)
                        if update_sale(original_idx, updated_entry):
                            st.success("Sale updated successfully!")
                            del st.session_state.edit_sale_idx
                            st.rerun()
                
                if st.button("Cancel Edit", key="cancel_sale_edit"):
                    del st.session_state.edit_sale_idx
                    st.rerun()
            
            # Summary metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Revenue", fmt(df["total_price"].sum()))
            c2.metric("Total Profit", fmt(df["profit"].sum()))
            c3.metric("Total Transactions", len(df))
        else:
            st.info("No sales records found for the selected date range")
    else:
        st.info("No sales recorded yet. Use the form above to add your first sale.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: EXPENSES (with edit/delete capabilities)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💸 Expenses":
    st.title("💸 Business Expenses")
    st.markdown("---")

    expenses = load_json(EXPENSES_FILE, [])
    CATEGORIES = ["Rent", "Transport / Delivery", "Electricity", "Water",
                  "Staff Wages", "Packaging", "Phone / Airtime", "Bank Charges",
                  "Repairs & Maintenance", "Other"]

    # ── Add new expense ───────────────────────────────────────────────────────
    with st.expander("➕ Add New Expense", expanded=True):
        with st.form("expense_form"):
            col1, col2 = st.columns(2)
            with col1:
                exp_date = st.date_input("Date", value=date.today())
                category = st.selectbox("Category", CATEGORIES)
            with col2:
                amount = st.number_input("Amount (TZS)", min_value=0, step=500)
                description = st.text_input("Description / Notes")

            if st.form_submit_button("💾 Save Expense"):
                expenses.append({
                    "date": str(exp_date),
                    "category": category,
                    "amount": amount,
                    "description": description,
                })
                save_json(EXPENSES_FILE, expenses)
                st.success(f"✅ Expense saved: {category} — {fmt(amount)}")
                st.rerun()

    st.markdown("---")

    # ── View, Edit, Delete Expenses ───────────────────────────────────────────
    st.subheader("📋 Expense Records")
    
    if expenses:
        # Date filters
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            view_option = st.selectbox("View by", ["All Records", "Specific Date", "Date Range", "Month/Year"], key="exp_view_option")
        
        filtered_expenses = expenses.copy()
        
        if view_option == "Specific Date":
            with col_f2:
                target_date = st.date_input("Select Date", value=date.today(), key="exp_target_date")
            filtered_expenses = get_records_by_date(expenses, target_date)
        elif view_option == "Date Range":
            with col_f2:
                start_date = st.date_input("Start Date", value=date.today() - timedelta(days=30), key="exp_start_date")
            with col_f3:
                end_date = st.date_input("End Date", value=date.today(), key="exp_end_date")
            filtered_expenses = get_records_by_date_range(expenses, start_date, end_date)
        elif view_option == "Month/Year":
            with col_f2:
                selected_month = st.selectbox("Month", range(1, 13), index=date.today().month - 1, key="exp_month")
            with col_f3:
                selected_year = st.number_input("Year", min_value=2020, max_value=2030, value=date.today().year, key="exp_year")
            filtered_expenses = get_records_by_month(expenses, selected_year, selected_month)
        
        if filtered_expenses:
            df = pd.DataFrame(filtered_expenses)
            df["display_date"] = pd.to_datetime(df["date"]).dt.strftime("%d %b %Y")
            
            st.write(f"**Found {len(filtered_expenses)} records**")
            
            # Display with edit/delete options
            for idx, row in df.iterrows():
                with st.container():
                    col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 2, 1, 1])
                    with col1:
                        st.write(row["display_date"])
                    with col2:
                        st.write(row["category"])
                    with col3:
                        st.write(row["description"] if pd.notna(row["description"]) else "-")
                    with col4:
                        st.write(fmt(row["amount"]))
                    with col5:
                        if st.button(f"✏️ Edit", key=f"edit_exp_{idx}_{row.get('date', idx)}"):
                            st.session_state.edit_exp_idx = idx
                            st.session_state.edit_exp_data = row.to_dict()
                            st.rerun()
                    with col6:
                        if st.button(f"🗑️ Delete", key=f"del_exp_{idx}_{row.get('date', idx)}"):
                            if delete_expense_by_index(expenses.index(row.to_dict())):
                                st.success("Expense deleted successfully!")
                                st.rerun()
                    st.divider()
            
            # Edit form
            if "edit_exp_idx" in st.session_state:
                st.subheader("✏️ Edit Expense Record")
                edit_data = st.session_state.edit_exp_data
                with st.form("edit_expense_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_date = st.date_input("Date", value=datetime.strptime(edit_data["date"], "%Y-%m-%d").date())
                        new_category = st.selectbox("Category", CATEGORIES, index=CATEGORIES.index(edit_data["category"]))
                    with col2:
                        new_amount = st.number_input("Amount (TZS)", value=float(edit_data["amount"]))
                        new_description = st.text_input("Description", value=edit_data.get("description", ""))
                    
                    if st.form_submit_button("💾 Save Changes"):
                        updated_entry = edit_data.copy()
                        updated_entry["date"] = str(new_date)
                        updated_entry["category"] = new_category
                        updated_entry["amount"] = new_amount
                        updated_entry["description"] = new_description
                        
                        original_idx = expenses.index(edit_data)
                        if update_expense(original_idx, updated_entry):
                            st.success("Expense updated successfully!")
                            del st.session_state.edit_exp_idx
                            st.rerun()
                
                if st.button("Cancel Edit", key="cancel_exp_edit"):
                    del st.session_state.edit_exp_idx
                    st.rerun()
            
            st.metric("Total Expenses", fmt(df["amount"].astype(float).sum()))
        else:
            st.info("No expense records found for the selected date range")
    else:
        st.info("No expenses recorded yet. Use the form above to add your first expense.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: PROFIT & SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Profit & Summary":
    st.title("📊 Profit & Business Summary")
    st.markdown("---")

    sales = load_json(SALES_FILE, [])
    expenses = load_json(EXPENSES_FILE, [])

    # Date range selector
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From Date", value=date.today() - timedelta(days=30), key="profit_start_date")
    with col2:
        end_date = st.date_input("To Date", value=date.today(), key="profit_end_date")
    
    filtered_sales = get_records_by_date_range(sales, start_date, end_date)
    filtered_expenses = get_records_by_date_range(expenses, start_date, end_date)
    
    sales_df = pd.DataFrame(filtered_sales) if filtered_sales else pd.DataFrame()
    expenses_df = pd.DataFrame(filtered_expenses) if filtered_expenses else pd.DataFrame()

    total_revenue = sales_df["total_price"].astype(float).sum() if not sales_df.empty else 0
    gross_profit = sales_df["profit"].astype(float).sum() if not sales_df.empty else 0
    total_expenses = expenses_df["amount"].astype(float).sum() if not expenses_df.empty else 0
    net_profit = gross_profit - total_expenses

    # Purchase cost calculation
    try:
        master_buying = 0
        if not master_df.empty:
            for idx, row in master_df.iterrows():
                price = safe_float(row.get("BUYING PRICE/CARTON", 0))
                cartons = safe_float(row.get("CTN(S)", 0))
                master_buying += price * cartons
        
        single_buying = 0
        if not single_df.empty:
            for idx, row in single_df.iterrows():
                price = safe_float(row.get("BUYING PRICE/CARTON", 0))
                cartons = safe_float(row.get("CTN(S)", 0))
                single_buying += price * cartons
        
        purchase_cost = master_buying + single_buying
    except Exception as e:
        purchase_cost = 0

    st.subheader(f"💼 Summary ({start_date.strftime('%d %b %Y')} - {end_date.strftime('%d %b %Y')})")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Stock Purchased (TZS)", fmt(purchase_cost))
    c2.metric("Total Sales Revenue (TZS)", fmt(total_revenue))
    c3.metric("Total Business Expenses (TZS)", fmt(total_expenses))

    st.markdown("---")
    c4, c5, c6 = st.columns(3)
    c4.metric("Gross Profit (from sales)", fmt(gross_profit))
    c5.metric("Less: Expenses", fmt(total_expenses))
    c6.metric("🏆 Net Profit", fmt(net_profit))

    st.markdown("---")

    if not sales_df.empty:
        st.subheader("📦 Profit by Item")
        item_summary = sales_df.groupby("item").agg(
            Total_Revenue=("total_price", "sum"),
            Total_Profit=("profit", "sum"),
            Transactions=("item", "count")
        ).reset_index().sort_values("Total_Profit", ascending=False)
        item_summary.columns = ["Item", "Revenue (TZS)", "Profit (TZS)", "Transactions"]
        for col in ["Revenue (TZS)", "Profit (TZS)"]:
            item_summary[col] = item_summary[col].apply(lambda x: fmt_price_only(safe_float(x)))
        st.dataframe(item_summary, use_container_width=True, hide_index=True)

    if not expenses_df.empty:
        st.subheader("💸 Expenses by Category")
        exp_summary = expenses_df.groupby("category")["amount"].sum().reset_index()
        exp_summary.columns = ["Category", "Total (TZS)"]
        exp_summary = exp_summary.sort_values("Total (TZS)", ascending=False)
        exp_summary["Total (TZS)"] = exp_summary["Total (TZS)"].apply(lambda x: fmt_price_only(safe_float(x)))
        st.dataframe(exp_summary, use_container_width=True, hide_index=True)

    if sales_df.empty and expenses_df.empty:
        st.info("No records found for the selected date range.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: CALENDAR VIEW
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🗓️ Calendar View":
    st.title("🗓️ Calendar View")
    st.markdown("---")
    
    sales = load_json(SALES_FILE, [])
    expenses = load_json(EXPENSES_FILE, [])
    
    # Year and Month selection
    col1, col2 = st.columns(2)
    with col1:
        selected_year = st.selectbox("Year", range(2020, 2031), index=date.today().year - 2020, key="calendar_year")
    with col2:
        selected_month = st.selectbox("Month", range(1, 13), index=date.today().month - 1, key="calendar_month")
    
    # Get month name
    month_name = calendar.month_name[selected_month]
    st.subheader(f"{month_name} {selected_year}")
    
    # Create calendar grid
    cal = calendar.monthcalendar(selected_year, selected_month)
    
    # Get records for the month
    month_sales = get_records_by_month(sales, selected_year, selected_month)
    month_expenses = get_records_by_month(expenses, selected_year, selected_month)
    
    # Create a dictionary to organize records by day
    sales_by_day = {}
    for sale in month_sales:
        day = int(sale["date"].split("-")[2])
        if day not in sales_by_day:
            sales_by_day[day] = []
        sales_by_day[day].append(sale)
    
    expenses_by_day = {}
    for expense in month_expenses:
        day = int(expense["date"].split("-")[2])
        if day not in expenses_by_day:
            expenses_by_day[day] = []
        expenses_by_day[day].append(expense)
    
    # Display calendar
    days_cols = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    header_cols = st.columns(7)
    for i, day_name in enumerate(days_cols):
        header_cols[i].markdown(f"**{day_name}**")
    
    for week in cal:
        week_cols = st.columns(7)
        for i, day in enumerate(week):
            with week_cols[i]:
                if day != 0:
                    st.markdown(f"**Day {day}**")
                    
                    # Show sales for this day
                    if day in sales_by_day:
                        total_sales_day = sum(s["total_price"] for s in sales_by_day[day])
                        st.markdown(f"💰 **Sales:** {fmt(total_sales_day)}")
                        st.markdown(f"📦 {len(sales_by_day[day])} transactions")
                    
                    # Show expenses for this day
                    if day in expenses_by_day:
                        total_expenses_day = sum(e["amount"] for e in expenses_by_day[day])
                        st.markdown(f"💸 **Expenses:** {fmt(total_expenses_day)}")
                    
                    # Show net for the day
                    if day in sales_by_day or day in expenses_by_day:
                        day_sales = sum(s["total_price"] for s in sales_by_day.get(day, []))
                        day_expenses = sum(e["amount"] for e in expenses_by_day.get(day, []))
                        day_profit = day_sales - day_expenses
                        st.markdown(f"**Net:** {fmt(day_profit)}")
                    
                    st.markdown("---")
    
    # Summary for the month
    st.subheader(f"📊 {month_name} {selected_year} Summary")
    col1, col2, col3 = st.columns(3)
    total_month_sales = sum(s["total_price"] for s in month_sales)
    total_month_expenses = sum(e["amount"] for e in month_expenses)
    total_month_profit = total_month_sales - total_month_expenses
    
    col1.metric("Total Sales", fmt(total_month_sales))
    col2.metric("Total Expenses", fmt(total_month_expenses))
    col3.metric("Net Profit", fmt(total_month_profit))

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: DATA MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "⚙️ Data Management":
    st.title("⚙️ Data Management")
    st.markdown("---")
    
    st.warning("⚠️ **Warning:** These actions are permanent and cannot be undone!")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Sales Data", "💸 Expenses Data", "📦 Inventory Data", "📋 Export Data"])
    
    with tab1:
        st.subheader("Sales Data Management")
        sales = load_json(SALES_FILE, [])
        st.write(f"**Current sales records: {len(sales)}**")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Delete All Sales Records", type="secondary", key="delete_all_sales_btn"):
                st.session_state.confirm_sales_delete = True
        
        with col2:
            if st.button("📊 View Sample", type="primary", key="view_sales_sample"):
                if sales:
                    st.json(sales[:3])
                else:
                    st.info("No sales records to display")
        
        if st.session_state.get("confirm_sales_delete", False):
            st.error("⚠️ Are you sure you want to delete ALL sales records?")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Yes, Delete All Sales", key="confirm_delete_sales"):
                    delete_all_sales()
                    st.success("All sales records have been deleted!")
                    st.session_state.confirm_sales_delete = False
                    st.rerun()
            with col2:
                if st.button("❌ No, Cancel", key="cancel_delete_sales"):
                    st.session_state.confirm_sales_delete = False
                    st.rerun()
    
    with tab2:
        st.subheader("Expenses Data Management")
        expenses = load_json(EXPENSES_FILE, [])
        st.write(f"**Current expense records: {len(expenses)}**")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Delete All Expense Records", type="secondary", key="delete_all_expenses_btn"):
                st.session_state.confirm_expenses_delete = True
        
        with col2:
            if st.button("📊 View Sample", type="primary", key="view_expenses_sample"):
                if expenses:
                    st.json(expenses[:3])
                else:
                    st.info("No expense records to display")
        
        if st.session_state.get("confirm_expenses_delete", False):
            st.error("⚠️ Are you sure you want to delete ALL expense records?")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Yes, Delete All Expenses", key="confirm_delete_expenses"):
                    delete_all_expenses()
                    st.success("All expense records have been deleted!")
                    st.session_state.confirm_expenses_delete = False
                    st.rerun()
            with col2:
                if st.button("❌ No, Cancel", key="cancel_delete_expenses"):
                    st.session_state.confirm_expenses_delete = False
                    st.rerun()
    
    with tab3:
        st.subheader("Inventory Data Management")
        inventory = load_json(INVENTORY_FILE, {})
        st.write(f"**Current inventory overrides: {len(inventory)} items**")
        
        if st.button("🔄 Reset All Inventory to Default (from Excel)", type="secondary", key="reset_inventory_btn"):
            st.session_state.confirm_inventory_reset = True
        
        if st.session_state.get("confirm_inventory_reset", False):
            st.error("⚠️ Are you sure you want to reset ALL inventory to default values?")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Yes, Reset Inventory", key="confirm_reset_inventory"):
                    delete_all_inventory_overrides()
                    st.success("All inventory has been reset to default values!")
                    st.session_state.confirm_inventory_reset = False
                    st.rerun()
            with col2:
                if st.button("❌ No, Cancel", key="cancel_reset_inventory"):
                    st.session_state.confirm_inventory_reset = False
                    st.rerun()
    
    with tab4:
        st.subheader("Export Data")
        
        sales = load_json(SALES_FILE, [])
        expenses = load_json(EXPENSES_FILE, [])
        
        if sales:
            sales_df = pd.DataFrame(sales)
            csv_sales = sales_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Sales Data (CSV)",
                data=csv_sales,
                file_name=f"sales_export_{date.today()}.csv",
                mime="text/csv",
                key="download_sales_csv"
            )
        
        if expenses:
            expenses_df = pd.DataFrame(expenses)
            csv_expenses = expenses_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Expenses Data (CSV)",
                data=csv_expenses,
                file_name=f"expenses_export_{date.today()}.csv",
                mime="text/csv",
                key="download_expenses_csv"
            )
        
        # Export combined summary
        if sales or expenses:
            summary_data = {
                "Export Date": str(date.today()),
                "Total Sales": sum(s.get("total_price", 0) for s in sales),
                "Total Profit": sum(s.get("profit", 0) for s in sales),
                "Total Expenses": sum(e.get("amount", 0) for e in expenses),
                "Net Profit": sum(s.get("profit", 0) for s in sales) - sum(e.get("amount", 0) for e in expenses),
                "Total Sales Records": len(sales),
                "Total Expense Records": len(expenses)
            }
            summary_df = pd.DataFrame([summary_data])
            csv_summary = summary_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Summary Report (CSV)",
                data=csv_summary,
                file_name=f"summary_report_{date.today()}.csv",
                mime="text/csv",
                key="download_summary_csv"
            )
