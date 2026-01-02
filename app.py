import sqlite3
import os
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- PASSWORD VALIDATION ----------------
def is_valid_password(password):
    if len(password) < 8:
        return False

    has_upper = has_lower = has_digit = has_special = False

    for ch in password:
        if ch.isupper():
            has_upper = True
        elif ch.islower():
            has_lower = True
        elif ch.isdigit():
            has_digit = True
        elif ch in "@#$!%&*":
            has_special = True

    return has_upper and has_lower and has_digit and has_special

# ---------------- PRODUCT DATA ----------------
PRODUCT_PRICES = {
    "shoes1": 1999,
    "shoes2": 1799,
    "shirt2": 999,
    "shirt3": 1099,
    "shirt4": 1199,
    "pant2": 1399,
    "pant3": 1299,
    "pant4": 1499,
    "watch1": 2499,
    "watch2": 2299,
    "watch3": 2199,
    "watch4": 2099
}

PRODUCT_NAMES = {
    "shoes1": "Sports Shoes",
    "shoes2": "Casual Shoes",
    "shirt2": "Formal Shirt",
    "shirt3": "Printed Shirt",
    "shirt4": "Denim Shirt",
    "pant2": "Jeans Pants",
    "pant3": "Cotton Pants",
    "pant4": "Formal Pants",
    "watch1": "Smart Watch",
    "watch2": "Leather Watch",
    "watch3": "Classic Watch",
    "watch4": "Digital Watch"
}

# ---------------- DATABASE ----------------
def get_db_connection():
    conn = sqlite3.connect("fashion.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT,
            user_email TEXT,
            items TEXT,
            total REAL,
            payment_method TEXT,
            order_time TEXT
        )
    """)

    conn.commit()
    conn.close()

# ✅ IMPORTANT: CREATE TABLES AT APP LOAD (RENDER FIX)
create_tables()

# ---------------- HOME ----------------
@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    cart = session.get("cart", {})
    cart_count = sum(cart.values())
    return render_template("index.html", cart_count=cart_count)

# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    message = ""

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            message = "Passwords do not match"
            return render_template("signup.html", message=message)

        if not is_valid_password(password):
            message = "Password must contain uppercase, lowercase, number & special character"
            return render_template("signup.html", message=message)

        hashed_password = generate_password_hash(password)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, hashed_password)
            )
            conn.commit()
            conn.close()
            message = "Account created successfully! Please login."

        except sqlite3.IntegrityError:
            message = "Email already exists."

    return render_template("signup.html", message=message)

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    message = ""

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("home"))
        else:
            message = "Invalid email or password"

    return render_template("login.html", message=message)

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------- CART ----------------
@app.route("/add-to-cart", methods=["POST"])
def add_to_cart():
    product = request.form["product"]

    if "cart" not in session:
        session["cart"] = {}

    session["cart"][product] = session["cart"].get(product, 0) + 1
    session.modified = True
    return redirect(url_for("home"))

@app.route("/update-cart", methods=["POST"])
def update_cart():
    product = request.form["product"]
    action = request.form["action"]

    if product in session.get("cart", {}):
        if action == "plus":
            session["cart"][product] += 1
        elif action == "minus":
            session["cart"][product] -= 1
            if session["cart"][product] <= 0:
                del session["cart"][product]

    session.modified = True
    return redirect(url_for("cart"))

@app.route("/cart")
def cart():
    if "user_id" not in session:
        return redirect(url_for("login"))

    cart = session.get("cart", {})
    subtotal = sum(PRODUCT_PRICES[p] * q for p, q in cart.items())
    gst = round(subtotal * 0.18, 2)
    discount = session.get("discount", 0)
    total = subtotal + gst - discount

    return render_template(
        "cart.html",
        cart_items=cart,
        prices=PRODUCT_PRICES,
        names=PRODUCT_NAMES,
        subtotal=subtotal,
        gst=gst,
        discount=discount,
        total=total
    )

# ---------------- COUPON ----------------
@app.route("/apply-coupon", methods=["POST"])
def apply_coupon():
    code = request.form["coupon"]
    session["discount"] = 100 if code == "SAVE100" else 200 if code == "SAVE200" else 0
    session.modified = True
    return redirect(url_for("cart"))

# ---------------- CHECKOUT ----------------
@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        payment_method = request.form.get("payment")
        if not payment_method:
            return redirect(url_for("checkout"))

        cart = session.get("cart", {})
        items = []
        total = 0

        for product, qty in cart.items():
            total += PRODUCT_PRICES.get(product, 0) * qty
            items.append(f"{product} x{qty}")

        items_str = ", ".join(items)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, email FROM users WHERE id = ?", (session["user_id"],))
        user = cursor.fetchone()

        cursor.execute("""
            INSERT INTO orders (user_name, user_email, items, total, payment_method, order_time)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user["name"],
            user["email"],
            items_str,
            total,
            payment_method,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()
        conn.close()

        session.pop("cart", None)
        session.pop("discount", None)
        return render_template("success.html")

    return render_template("checkout.html")

# ---------------- ADMIN ----------------
@app.route("/admin/orders")
def admin_orders():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders ORDER BY id DESC")
    orders = cursor.fetchall()
    conn.close()
    return render_template("admin_orders.html", orders=orders)

# ---------------- MAIN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

