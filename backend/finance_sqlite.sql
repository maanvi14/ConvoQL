-- ============================================
-- CONVOQL TEST DATABASE: finance.db (SQLite) 2026 data (Jan-May)
-- ============================================

-- ============================================
-- TABLE: transactions
-- Core table for SQL generation & insight tests
-- ============================================
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    description TEXT,
    amount REAL NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('credit', 'debit')),
    category TEXT NOT NULL,
    account TEXT NOT NULL,
    merchant TEXT,
    payment_method TEXT DEFAULT 'Card' CHECK(payment_method IN ('UPI', 'Card', 'NetBanking', 'Cash', 'Cheque')),
    tags TEXT
);

-- ============================================
-- DATASET: 2026 Jan-May realistic transactions
-- ============================================

-- JANUARY 2026 (Baseline month)
INSERT INTO transactions (date, description, amount, type, category, account, merchant, payment_method, tags) VALUES
('2026-01-01', 'Salary Credited', 80000.00, 'credit', 'Income', 'HDFC', 'Employer Inc', 'NetBanking', 'salary,monthly'),
('2026-01-02', 'Rent Payment', -28000.00, 'debit', 'Housing', 'HDFC', 'Landlord', 'NetBanking', 'rent,monthly'),
('2026-01-03', 'Big Bazaar Grocery', -4500.00, 'debit', 'Groceries', 'HDFC', 'Big Bazaar', 'UPI', 'grocery,monthly'),
('2026-01-05', 'Amazon Purchase', -4200.00, 'debit', 'Shopping', 'ICICI', 'Amazon', 'Card', 'electronics'),
('2026-01-07', 'Electricity Bill', -3200.00, 'debit', 'Utilities', 'HDFC', 'State Electricity', 'NetBanking', 'bill,monthly'),
('2026-01-08', 'Freelance Project', 18000.00, 'credit', 'Side Income', 'Paytm', 'Client A', 'UPI', 'freelance,project'),
('2026-01-10', 'Netflix Subscription', -649.00, 'debit', 'Entertainment', 'ICICI', 'Netflix', 'Card', 'subscription'),
('2026-01-12', 'Petrol Pump', -2400.00, 'debit', 'Transport', 'HDFC', 'Indian Oil', 'UPI', 'fuel'),
('2026-01-14', 'Zomato Order', -950.00, 'debit', 'Food', 'HDFC', 'Zomato', 'UPI', 'food,weekend'),
('2026-01-15', 'Mobile Recharge', -399.00, 'debit', 'Utilities', 'Paytm', 'Jio', 'UPI', 'recharge'),
('2026-01-16', 'Gym Membership', -1800.00, 'debit', 'Fitness', 'HDFC', 'Gold Gym', 'Card', 'subscription,health'),
('2026-01-18', 'Medical Store', -1400.00, 'debit', 'Health', 'ICICI', 'Apollo Pharmacy', 'UPI', 'medicine'),
('2026-01-20', 'Stock Dividend', 4500.00, 'credit', 'Investment', 'ICICI', 'Zerodha', 'NetBanking', 'dividend,passive'),
('2026-01-22', 'ATM Withdrawal', -5500.00, 'debit', 'Cash', 'HDFC', 'HDFC ATM', 'Cash', 'cash'),
('2026-01-25', 'Uber Ride', -480.00, 'debit', 'Transport', 'Paytm', 'Uber', 'UPI', 'cab'),
('2026-01-28', 'Spotify Premium', -199.00, 'debit', 'Entertainment', 'ICICI', 'Spotify', 'Card', 'subscription'),
('2026-01-30', 'Year-End Bonus', 25000.00, 'credit', 'Income', 'HDFC', 'Employer Inc', 'NetBanking', 'bonus,annual');

-- FEBRUARY 2026 (Higher spending - trend test)
INSERT INTO transactions (date, description, amount, type, category, account, merchant, payment_method, tags) VALUES
('2026-02-01', 'Salary Credited', 80000.00, 'credit', 'Income', 'HDFC', 'Employer Inc', 'NetBanking', 'salary,monthly'),
('2026-02-01', 'Rent Payment', -28000.00, 'debit', 'Housing', 'HDFC', 'Landlord', 'NetBanking', 'rent,monthly'),
('2026-02-02', 'DMart Grocery', -5200.00, 'debit', 'Groceries', 'HDFC', 'DMart', 'UPI', 'grocery,monthly'),
('2026-02-04', 'Flipkart Sale', -6800.00, 'debit', 'Shopping', 'ICICI', 'Flipkart', 'Card', 'electronics,sale'),
('2026-02-06', 'Electricity Bill', -3500.00, 'debit', 'Utilities', 'HDFC', 'State Electricity', 'NetBanking', 'bill,monthly'),
('2026-02-08', 'Freelance Project', 15000.00, 'credit', 'Side Income', 'Paytm', 'Client B', 'UPI', 'freelance'),
('2026-02-10', 'Netflix Subscription', -649.00, 'debit', 'Entertainment', 'ICICI', 'Netflix', 'Card', 'subscription'),
('2026-02-11', 'Petrol Pump', -2600.00, 'debit', 'Transport', 'HDFC', 'Bharat Petroleum', 'UPI', 'fuel'),
('2026-02-13', 'Swiggy Order', -1300.00, 'debit', 'Food', 'HDFC', 'Swiggy', 'UPI', 'food,weekend'),
('2026-02-14', 'Valentine Dinner', -4200.00, 'debit', 'Food', 'ICICI', 'Taj Restaurant', 'Card', 'food,special'),
('2026-02-15', 'Mobile Recharge', -399.00, 'debit', 'Utilities', 'Paytm', 'Jio', 'UPI', 'recharge'),
('2026-02-16', 'Gym Membership', -1800.00, 'debit', 'Fitness', 'HDFC', 'Gold Gym', 'Card', 'subscription'),
('2026-02-18', 'Medical Store', -1100.00, 'debit', 'Health', 'ICICI', 'Apollo Pharmacy', 'UPI', 'medicine'),
('2026-02-20', 'Consulting Fee', 35000.00, 'credit', 'Side Income', 'HDFC', 'Client C', 'NetBanking', 'consulting'),
('2026-02-22', 'ATM Withdrawal', -4500.00, 'debit', 'Cash', 'HDFC', 'HDFC ATM', 'Cash', 'cash'),
('2026-02-25', 'Ola Ride', -420.00, 'debit', 'Transport', 'Paytm', 'Ola', 'UPI', 'cab'),
('2026-02-26', 'Movie Tickets', -1500.00, 'debit', 'Entertainment', 'ICICI', 'PVR Cinemas', 'UPI', 'movie,weekend'),
('2026-02-28', 'Laptop Purchase', -75000.00, 'debit', 'Shopping', 'ICICI', 'Apple Store', 'Card', 'electronics,anomaly,big');

-- MARCH 2026 (Anomaly: Big vacation spending)
INSERT INTO transactions (date, description, amount, type, category, account, merchant, payment_method, tags) VALUES
('2026-03-01', 'Salary Credited', 85000.00, 'credit', 'Income', 'HDFC', 'Employer Inc', 'NetBanking', 'salary,monthly,raise'),
('2026-03-01', 'Rent Payment', -28000.00, 'debit', 'Housing', 'HDFC', 'Landlord', 'NetBanking', 'rent,monthly'),
('2026-03-02', 'Reliance Fresh', -4300.00, 'debit', 'Groceries', 'HDFC', 'Reliance Fresh', 'UPI', 'grocery,monthly'),
('2026-03-03', 'Flight to Bali', -45000.00, 'debit', 'Travel', 'ICICI', 'MakeMyTrip', 'Card', 'travel,anomaly,vacation'),
('2026-03-05', 'Electricity Bill', -3100.00, 'debit', 'Utilities', 'HDFC', 'State Electricity', 'NetBanking', 'bill,monthly'),
('2026-03-07', 'Freelance Project', 22000.00, 'credit', 'Side Income', 'Paytm', 'Client D', 'UPI', 'freelance'),
('2026-03-09', 'Netflix Subscription', -649.00, 'debit', 'Entertainment', 'ICICI', 'Netflix', 'Card', 'subscription'),
('2026-03-10', 'Petrol Pump', -2300.00, 'debit', 'Transport', 'HDFC', 'Indian Oil', 'UPI', 'fuel'),
('2026-03-12', 'Zomato Order', -1100.00, 'debit', 'Food', 'HDFC', 'Zomato', 'UPI', 'food,weekend'),
('2026-03-14', 'Amazon Purchase', -3200.00, 'debit', 'Shopping', 'ICICI', 'Amazon', 'Card', 'electronics'),
('2026-03-15', 'Mobile Recharge', -399.00, 'debit', 'Utilities', 'Paytm', 'Jio', 'UPI', 'recharge'),
('2026-03-16', 'Gym Membership', -1800.00, 'debit', 'Fitness', 'HDFC', 'Gold Gym', 'Card', 'subscription'),
('2026-03-17', 'Medical Store', -1800.00, 'debit', 'Health', 'ICICI', 'Apollo Pharmacy', 'UPI', 'medicine'),
('2026-03-19', 'Stock Dividend', 5500.00, 'credit', 'Investment', 'ICICI', 'Zerodha', 'NetBanking', 'dividend'),
('2026-03-21', 'ATM Withdrawal', -7000.00, 'debit', 'Cash', 'HDFC', 'HDFC ATM', 'Cash', 'cash'),
('2026-03-23', 'Uber Ride', -580.00, 'debit', 'Transport', 'Paytm', 'Uber', 'UPI', 'cab'),
('2026-03-25', 'Spotify Premium', -199.00, 'debit', 'Entertainment', 'ICICI', 'Spotify', 'Card', 'subscription'),
('2026-03-27', 'Myntra Shopping', -4200.00, 'debit', 'Shopping', 'ICICI', 'Myntra', 'Card', 'clothing'),
('2026-03-29', 'Croma Electronics', -15500.00, 'debit', 'Shopping', 'ICICI', 'Croma', 'Card', 'electronics,anomaly'),
('2026-03-30', 'Dinner Party', -5200.00, 'debit', 'Food', 'HDFC', 'Social Restaurant', 'Card', 'food,social');

-- APRIL 2026 (Stable month - post vacation recovery)
INSERT INTO transactions (date, description, amount, type, category, account, merchant, payment_method, tags) VALUES
('2026-04-01', 'Salary Credited', 85000.00, 'credit', 'Income', 'HDFC', 'Employer Inc', 'NetBanking', 'salary,monthly'),
('2026-04-01', 'Rent Payment', -28000.00, 'debit', 'Housing', 'HDFC', 'Landlord', 'NetBanking', 'rent,monthly'),
('2026-04-02', 'Big Bazaar Grocery', -4400.00, 'debit', 'Groceries', 'HDFC', 'Big Bazaar', 'UPI', 'grocery,monthly'),
('2026-04-03', 'Amazon Purchase', -2100.00, 'debit', 'Shopping', 'ICICI', 'Amazon', 'Card', 'home'),
('2026-04-05', 'Electricity Bill', -3400.00, 'debit', 'Utilities', 'HDFC', 'State Electricity', 'NetBanking', 'bill,monthly'),
('2026-04-07', 'Freelance Project', 12000.00, 'credit', 'Side Income', 'Paytm', 'Client E', 'UPI', 'freelance'),
('2026-04-09', 'Netflix Subscription', -649.00, 'debit', 'Entertainment', 'ICICI', 'Netflix', 'Card', 'subscription'),
('2026-04-10', 'Petrol Pump', -2500.00, 'debit', 'Transport', 'HDFC', 'Indian Oil', 'UPI', 'fuel'),
('2026-04-12', 'Zomato Order', -880.00, 'debit', 'Food', 'HDFC', 'Zomato', 'UPI', 'food,weekend'),
('2026-04-13', 'Croma Return Refund', 15500.00, 'credit', 'Shopping', 'ICICI', 'Croma', 'Card', 'refund,return'),
('2026-04-15', 'Mobile Recharge', -399.00, 'debit', 'Utilities', 'Paytm', 'Jio', 'UPI', 'recharge'),
('2026-04-16', 'Gym Membership', -1800.00, 'debit', 'Fitness', 'HDFC', 'Gold Gym', 'Card', 'subscription'),
('2026-04-18', 'Medical Store', -1600.00, 'debit', 'Health', 'ICICI', 'Apollo Pharmacy', 'UPI', 'medicine'),
('2026-04-20', 'Stock Loss', -12000.00, 'debit', 'Investment', 'ICICI', 'Zerodha', 'NetBanking', 'stock,loss,anomaly'),
('2026-04-22', 'ATM Withdrawal', -4000.00, 'debit', 'Cash', 'HDFC', 'HDFC ATM', 'Cash', 'cash'),
('2026-04-24', 'Uber Ride', -350.00, 'debit', 'Transport', 'Paytm', 'Uber', 'UPI', 'cab'),
('2026-04-26', 'Spotify Premium', -199.00, 'debit', 'Entertainment', 'ICICI', 'Spotify', 'Card', 'subscription'),
('2026-04-28', 'Flight Booking', -9500.00, 'debit', 'Travel', 'ICICI', 'MakeMyTrip', 'Card', 'travel,flight'),
('2026-04-29', 'Hotel Booking', -7200.00, 'debit', 'Travel', 'ICICI', 'Booking.com', 'Card', 'travel,hotel');

-- MAY 2026 (Current month - partial, for "this month" queries)
INSERT INTO transactions (date, description, amount, type, category, account, merchant, payment_method, tags) VALUES
('2026-05-01', 'Salary Credited', 90000.00, 'credit', 'Income', 'HDFC', 'Employer Inc', 'NetBanking', 'salary,monthly,raise'),
('2026-05-01', 'Rent Payment', -28000.00, 'debit', 'Housing', 'HDFC', 'Landlord', 'NetBanking', 'rent,monthly'),
('2026-05-02', 'DMart Grocery', -4800.00, 'debit', 'Groceries', 'HDFC', 'DMart', 'UPI', 'grocery,monthly'),
('2026-05-03', 'Amazon Purchase', -2600.00, 'debit', 'Shopping', 'ICICI', 'Amazon', 'Card', 'home'),
('2026-05-04', 'Electricity Bill', -3600.00, 'debit', 'Utilities', 'HDFC', 'State Electricity', 'NetBanking', 'bill,monthly,high'),
('2026-05-05', 'Freelance Project', 28000.00, 'credit', 'Side Income', 'Paytm', 'Client F', 'UPI', 'freelance'),
('2026-05-07', 'Netflix Subscription', -649.00, 'debit', 'Entertainment', 'ICICI', 'Netflix', 'Card', 'subscription'),
('2026-05-08', 'Petrol Pump', -2800.00, 'debit', 'Transport', 'HDFC', 'Indian Oil', 'UPI', 'fuel'),
('2026-05-09', 'Zomato Order', -1400.00, 'debit', 'Food', 'HDFC', 'Zomato', 'UPI', 'food,weekend'),
('2026-05-10', 'Swiggy Order', -950.00, 'debit', 'Food', 'HDFC', 'Swiggy', 'UPI', 'food'),
('2026-05-11', 'Mobile Recharge', -399.00, 'debit', 'Utilities', 'Paytm', 'Jio', 'UPI', 'recharge'),
('2026-05-12', 'Gym Membership', -1800.00, 'debit', 'Fitness', 'HDFC', 'Gold Gym', 'Card', 'subscription'),
('2026-05-13', 'Medical Store', -750.00, 'debit', 'Health', 'ICICI', 'Apollo Pharmacy', 'UPI', 'medicine'),
('2026-05-14', 'Stock Dividend', 6000.00, 'credit', 'Investment', 'ICICI', 'Zerodha', 'NetBanking', 'dividend'),
('2026-05-15', 'ATM Withdrawal', -5000.00, 'debit', 'Cash', 'HDFC', 'HDFC ATM', 'Cash', 'cash'),
('2026-05-16', 'Uber Ride', -390.00, 'debit', 'Transport', 'Paytm', 'Uber', 'UPI', 'cab'),
('2026-05-17', 'Spotify Premium', -199.00, 'debit', 'Entertainment', 'ICICI', 'Spotify', 'Card', 'subscription'),
('2026-05-18', 'Movie Tickets', -1800.00, 'debit', 'Entertainment', 'ICICI', 'PVR Cinemas', 'UPI', 'movie'),
('2026-05-20', 'Laptop Repair', -4200.00, 'debit', 'Shopping', 'ICICI', 'Apple Service', 'Card', 'repair'),
('2026-05-22', 'Flight Booking', -14000.00, 'debit', 'Travel', 'ICICI', 'MakeMyTrip', 'Card', 'travel,anomaly');

-- ============================================
-- ADDITIONAL TABLES for multi-table JOIN tests
-- ============================================

-- Categories reference table
CREATE TABLE IF NOT EXISTS categories (
    category_name TEXT PRIMARY KEY,
    category_type TEXT NOT NULL CHECK(category_type IN ('income', 'expense', 'both')),
    budget_limit REAL,
    color_code TEXT,
    icon TEXT
);

INSERT INTO categories (category_name, category_type, budget_limit, color_code, icon) VALUES
('Income', 'income', NULL, '#22c55e', 'wallet'),
('Side Income', 'income', NULL, '#16a34a', 'briefcase'),
('Investment', 'both', NULL, '#3b82f6', 'trending-up'),
('Housing', 'expense', 28000.00, '#ef4444', 'home'),
('Groceries', 'expense', 5000.00, '#f97316', 'shopping-cart'),
('Shopping', 'expense', 10000.00, '#ec4899', 'shopping-bag'),
('Utilities', 'expense', 4000.00, '#eab308', 'zap'),
('Entertainment', 'expense', 5000.00, '#8b5cf6', 'film'),
('Transport', 'expense', 3000.00, '#06b6d4', 'car'),
('Food', 'expense', 6000.00, '#f43f5e', 'utensils'),
('Health', 'expense', 3000.00, '#14b8a6', 'heart-pulse'),
('Fitness', 'expense', 2000.00, '#84cc16', 'dumbbell'),
('Travel', 'expense', 15000.00, '#6366f1', 'plane'),
('Cash', 'expense', 5000.00, '#78716c', 'banknote');

-- Accounts reference table
CREATE TABLE IF NOT EXISTS accounts (
    account_name TEXT PRIMARY KEY,
    account_type TEXT NOT NULL CHECK(account_type IN ('savings', 'current', 'wallet', 'investment')),
    bank_name TEXT,
    balance REAL,
    currency TEXT DEFAULT 'INR',
    is_primary INTEGER DEFAULT 0
);

INSERT INTO accounts (account_name, account_type, bank_name, balance, is_primary) VALUES
('HDFC', 'savings', 'HDFC Bank', 145000.00, 1),
('ICICI', 'savings', 'ICICI Bank', 95000.00, 0),
('Paytm', 'wallet', 'Paytm Payments Bank', 35000.00, 0);

-- Budget tracking table
CREATE TABLE IF NOT EXISTS budgets (
    budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
    month_year DATE NOT NULL,
    category TEXT NOT NULL,
    allocated REAL NOT NULL,
    spent REAL DEFAULT 0,
    FOREIGN KEY (category) REFERENCES categories(category_name)
);

INSERT INTO budgets (month_year, category, allocated, spent) VALUES
('2026-01-01', 'Groceries', 5000.00, 4500.00),
('2026-01-01', 'Shopping', 8000.00, 4200.00),
('2026-01-01', 'Entertainment', 3000.00, 848.00),
('2026-02-01', 'Groceries', 5000.00, 5200.00),
('2026-02-01', 'Shopping', 8000.00, 75000.00),
('2026-02-01', 'Entertainment', 3000.00, 2149.00),
('2026-02-01', 'Food', 5000.00, 5500.00),
('2026-03-01', 'Groceries', 5000.00, 4300.00),
('2026-03-01', 'Shopping', 8000.00, 19700.00),
('2026-03-01', 'Entertainment', 3000.00, 848.00),
('2026-03-01', 'Travel', 15000.00, 45000.00),
('2026-04-01', 'Groceries', 5000.00, 4400.00),
('2026-04-01', 'Shopping', 8000.00, -13400.00),
('2026-04-01', 'Travel', 15000.00, 16700.00),
('2026-04-01', 'Investment', 10000.00, 12000.00),
('2026-05-01', 'Groceries', 5000.00, 4800.00),
('2026-05-01', 'Shopping', 8000.00, 2600.00),
('2026-05-01', 'Travel', 15000.00, 14000.00),
('2026-05-01', 'Utilities', 4000.00, 3600.00),
('2026-05-01', 'Food', 6000.00, 2350.00);

-- ============================================
-- VERIFICATION QUERIES (SQLite compatible)
-- ============================================

-- Total transactions
SELECT COUNT(*) AS total_transactions FROM transactions;

-- Transactions by month
SELECT 
    strftime('%Y-%m', date) AS month,
    COUNT(*) AS count,
    SUM(CASE WHEN type = 'credit' THEN amount ELSE 0 END) AS total_income,
    SUM(CASE WHEN type = 'debit' THEN amount ELSE 0 END) AS total_expense
FROM transactions
GROUP BY strftime('%Y-%m', date)
ORDER BY month;

-- May 2026 spending by category
SELECT 
    category,
    SUM(ABS(amount)) AS total_spent,
    COUNT(*) AS transaction_count
FROM transactions
WHERE type = 'debit' AND strftime('%Y-%m', date) = '2026-05'
GROUP BY category
ORDER BY total_spent DESC;

-- Top 10 largest transactions (anomaly proxy since SQLite has no STDEV)
SELECT 
    description,
    amount,
    category,
    date
FROM transactions
ORDER BY ABS(amount) DESC
LIMIT 10;

-- Budget vs Actual (May 2026)
SELECT 
    b.category,
    b.allocated,
    b.spent,
    ROUND((b.spent / b.allocated) * 100, 2) AS pct_used,
    CASE 
        WHEN b.spent > b.allocated THEN 'OVER BUDGET'
        WHEN b.spent > b.allocated * 0.8 THEN 'WARNING'
        ELSE 'OK'
    END AS status
FROM budgets b
WHERE strftime('%Y-%m', b.month_year) = '2026-05';