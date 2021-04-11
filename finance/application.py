import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    stockValues = 0
    """Show portfolio of stocks"""
    rows1 = db.execute("""
    SELECT symbol, SUM(quantity) as totalShares
    FROM transactions
    WHERE user_id = :user_id
    GROUP BY 1
    HAVING totalShares>0
    """, user_id = session["user_id"])
    portfolios = []
    for row in rows1:
        stock = lookup(row['symbol'])
        portfolios.append({
        "symbol" : stock["name"],
        "quantity" : row["totalShares"],
        "current_price" : stock["price"],
        "total_value" : stock["price"] * row["totalShares"]
        })
        total_value = stock["price"] * row["totalShares"]
        stockValues += total_value
    rows2 = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id = session["user_id"])
    cash_left = rows2[0]["cash"]
    grand_total = cash_left + stockValues
    return render_template('index.html', portfolios = portfolios, cash_left = cash_left, grand_total = grand_total)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        quantity = request.form.get("shares")
        if not symbol:
            return apology("Missing symbol", 400)
        if not quantity:
            return apology ("Missing symbol", 400)
        if not quantity.isdigit() or int(quantity)<1:
            return apology ("Invalid shares", 400)
        stock = lookup(symbol)
        if not stock:
            return apology("invalid symbol", 400)
        rows = db.execute("SELECT cash FROM users WHERE id = :uid", uid = session["user_id"])
        cash = rows[0]["cash"]
        stock_price = stock["price"]
        total_amount = int(quantity) * stock_price
        if cash< total_amount:
            return apology("Not enough cash!" ,400)
        else:
            db.execute("UPDATE users SET cash = cash - :value WHERE id = :uid", value = total_amount, uid = session["user_id"])
            db.execute("INSERT INTO transactions (user_id, symbol, quantity, total_amount, price) VALUES (:user_id, :symbol, :quantity, :total_amount, :price)", user_id=session["user_id"], symbol = stock["symbol"], quantity = quantity, total_amount=total_amount, price = stock_price)
        flash("bought!")
        return redirect('/')
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT symbol, quantity, price FROM transactions WHERE user_id = :user_id", user_id = session["user_id"])
    if rows is None:
        return apology("no transactions")
    for i in range(len(rows)):
        rows[i]["price"] = usd (rows[i]["price"])
    return render_template("history.html", transactions = rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Missing symbol!", 400)
        stock = lookup(symbol)
        if not stock:
            return apology ("no such stock")
        return render_template('quote_results.html', name = stock["name"], price = stock["price"], symbol = stock["symbol"])
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    username = request.form.get("username")
    password = request.form.get("password")
    confirmation = request.form.get("confirmation")
    if request.method == "POST":
    #error checking
        if not request.form.get("username"):
            return apology("Missing username!", 400)
        elif not request.form.get("password"):
            return apology("Missing password!")
        elif password!= confirmation:
            return apology("password and confirmation do not match!")
        #insert user into database
        hash = generate_password_hash(password)

        key = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username= username, hash = hash)
        if not key:
            return apology("cannnot be registered", 400)
        #login the user to the session
        rows = db.execute("SELECT * FROM users WHERE username = :username", username = username)
        session["user_id"] = rows[0]["id"]
        return redirect ('/')

    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Buy shares of stock"""
    symbol = request.form.get("symbol")
    quantity = request.form.get("quantity")
    if request.method == "POST":
        if not symbol:
            return apology("Missing symbol", 400)
        if not quantity:
            return apology ("Missing symbol", 400)
        stock = lookup(symbol)
        if stock is None:
            return apology('Stock not found')
        rows = db.execute("""
        SELECT symbol, SUM(quantity) as totalShares
        FROM transactions WHERE user_id = :user_id
        GROUP BY symbol
        Having totalShares >0;
        """, user_id = session["user_id"])
        for row in rows:
            if symbol == row["symbol"]:
                if int(quantity) > row["totalShares"]:
                    return apology ("Not enough shares to sell")

        rows = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
        cash = rows[0]["cash"]
        stock_price = stock["price"]
        cash_updated = int(cash) + int(quantity) *int(stock['price'])
        db.execute("UPDATE users SET cash = :value WHERE id = :id", value = cash_updated, id = session["user_id"])
        db.execute("INSERT INTO transactions (user_id, symbol, quantity, total_amount, price) VALUES (:user_id, :symbol, :quantity, :total_amount, :price)", user_id=session["user_id"], symbol = stock["symbol"], quantity = quantity, total_amount=cash_updated, price = stock_price)
        flash("Sold!")
        return redirect('/')

    else:
        rows = db.execute("""
        SELECT symbol FROM transactions WHERE user_id = :user_id
        GROUP BY symbol
        HAVING SUM(quantity)>0;
        """, user_id = session["user_id"])
        return render_template("sell.html", symbols = [row["symbol"] for row in rows])


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
