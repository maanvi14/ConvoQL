import sqlite3
import pymysql
from decimal import Decimal

# Connect to MySQL
mysql = pymysql.connect(host='localhost', user='root', password='Maanvi2006', database='finance_db')
cur = mysql.cursor()

# Create SQLite file
conn = sqlite3.connect('finance.db')
c = conn.cursor()

# Create tables
c.execute("""CREATE TABLE transactions (
    transaction_id INTEGER PRIMARY KEY,
    date TEXT, description TEXT, amount REAL,
    type TEXT, category TEXT, account TEXT,
    merchant TEXT, payment_method TEXT, tags TEXT)""")

c.execute("""CREATE TABLE categories (
    category_name TEXT PRIMARY KEY, category_type TEXT,
    budget_limit REAL, color_code TEXT, icon TEXT)""")

c.execute("""CREATE TABLE accounts (
    account_name TEXT PRIMARY KEY, account_type TEXT,
    bank_name TEXT, balance REAL, currency TEXT, is_primary INTEGER)""")

c.execute("""CREATE TABLE budgets (
    budget_id INTEGER PRIMARY KEY, month_year TEXT,
    category TEXT, allocated REAL, spent REAL)""")

# Helper to convert row data
def convert_row(row):
    new_row = []
    for val in row:
        if isinstance(val, Decimal):
            new_row.append(float(val))
        else:
            new_row.append(val)
    return new_row

# Copy data from MySQL
for table in ['transactions', 'categories', 'accounts', 'budgets']:
    cur.execute(f"SELECT * FROM {table}")
    rows = cur.fetchall()

    if not rows:
        print(f"{table}: 0 rows")
        continue

    # Convert Decimal to float for SQLite compatibility
    converted_rows = [convert_row(row) for row in rows]

    # Get column count
    num_cols = len(converted_rows[0])
    ph = ','.join(['?' for _ in range(num_cols)])

    c.executemany(f"INSERT INTO {table} VALUES ({ph})", converted_rows)
    print(f"✅ {table}: {len(rows)} rows copied")

conn.commit()
conn.close()
mysql.close()
print("\n🎉 finance.db created successfully!")