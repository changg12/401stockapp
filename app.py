from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session
from flask_bootstrap import Bootstrap4
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from math import ceil
from sqlalchemy import func

app = Flask(__name__)
bootstrap = Bootstrap4(app)

# ------------------------- Config -------------------------
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:password@localhost/flask_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'awdasdawdasdawdasdawdasd'

db = SQLAlchemy(app)

# ------------------------- Models -------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    phone_number = db.Column(db.BigInteger)
    address = db.Column(db.String(255))
    credit_card_name = db.Column(db.String(100))
    credit_card_last4 = db.Column(db.Integer)
    credit_card_expiration = db.Column(db.String(7))  # MM/YYYY
    checking_account_name = db.Column(db.String(100))
    checking_account_last4 = db.Column(db.Integer)
    checking_routing_number = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, server_default=db.func.now())


class PortfolioHolding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    shares = db.Column(db.Float, nullable=False)
    average_price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'symbol', name='unique_symbol_per_user'),)


class StockSymbol(db.Model):
    __tablename__ = 'stock_symbols'
    __table_args__ = {'extend_existing': True}
    market = db.Column(db.String(10), primary_key=True)
    symbol = db.Column(db.String(16), primary_key=True)
    name = db.Column(db.Text)
    lastsale = db.Column(db.Float)
    netchange = db.Column(db.Float)
    pctchange = db.Column(db.Float)
    volume = db.Column(db.Float)
    market_cap = db.Column('marketCap', db.Float)
    country = db.Column(db.Text)
    industry = db.Column(db.Text)
    sector = db.Column(db.Text)

# ------------------------- Helpers -------------------------
def _is_safe_next(url: str) -> bool:
    return isinstance(url, str) and url.startswith("/")

# ------------------------- Routes -------------------------
@app.route("/")
def home():
    markets = ["NASDAQ", "NYSE", "AMEX"]

    avg_pct_change = []
    for market in markets:
        sum_value, count_value = (
            db.session.query(
                func.coalesce(func.sum(StockSymbol.pctchange), 0),
                func.count(StockSymbol.symbol),
            )
            .filter(StockSymbol.market == market)
            .one()
        )
        avg_value = (sum_value / count_value) if count_value else 0
        avg_pct_change.append(round(avg_value, 4))

    per_page = 150
    stocks_by_market = {}
    market_pagination = {}
    existing_args = request.args.to_dict()

    for market in markets:
        param_name = f"{market.lower()}_page"
        page = request.args.get(param_name, default=1, type=int)

        base_query = StockSymbol.query.filter_by(market=market).order_by(StockSymbol.symbol)
        total_items = base_query.count()
        total_pages = max(ceil(total_items / per_page), 1)
        page = min(max(page, 1), total_pages)

        symbols = base_query.offset((page - 1) * per_page).limit(per_page).all()

        def build_page_items(current_page, total_pages_count):
            if total_pages_count <= 7:
                return [{"number": n, "ellipsis": False} for n in range(1, total_pages_count + 1)]
            items = []
            def add_number(n):
                if not any(x.get("number") == n for x in items):
                    items.append({"number": n, "ellipsis": False})
            add_number(1)
            if current_page > 4:
                items.append({"number": None, "ellipsis": True})
            for n in range(current_page - 1, current_page + 2):
                if 1 < n < total_pages_count:
                    add_number(n)
            if current_page < total_pages_count - 3:
                items.append({"number": None, "ellipsis": True})
            add_number(total_pages_count)
            return items

        page_items = build_page_items(page, total_pages)

        pagination_links = []
        for item in page_items:
            if item["ellipsis"]:
                pagination_links.append({"label": "…", "active": False, "disabled": True})
            else:
                args = existing_args.copy()
                args[param_name] = item["number"]
                pagination_links.append(
                    {"label": str(item["number"]), "url": url_for("home", **args),
                     "active": item["number"] == page, "disabled": False}
                )

        prev_args = existing_args.copy(); prev_args[param_name] = max(page - 1, 1)
        next_args = existing_args.copy(); next_args[param_name] = min(page + 1, total_pages)

        market_pagination[market] = {
            "page": page, "total_pages": total_pages, "total_items": total_items,
            "per_page": per_page, "prev_url": url_for("home", **prev_args),
            "next_url": url_for("home", **next_args), "has_prev": page > 1,
            "has_next": page < total_pages, "links": pagination_links, "param_name": param_name,
        }
        stocks_by_market[market] = symbols

    return render_template("stock.html",
                           markets=markets,
                           avg_pct_change=avg_pct_change,
                           stocks_by_market=stocks_by_market,
                           market_pagination=market_pagination)

@app.route("/dashboard")
def dashboard():
    return redirect(url_for("home"))

# -------- Login with non-stacking alert --------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        if not email or not password:
            return redirect(url_for("login", error="1"))

        user = User.query.filter(func.lower(User.email) == email).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['user_name'] = user.full_name
            next_url = request.args.get("next") or request.form.get("next")
            if _is_safe_next(next_url):
                return redirect(next_url)
            return redirect(url_for("dashboard"))

        # Wrong creds -> single error flag in query string
        next_url = request.args.get("next") or request.form.get("next") or ""
        return redirect(url_for("login", error="1", next=next_url))

    # GET
    error = request.args.get("error") == "1"
    next_url = request.args.get("next") or ""
    return render_template("login.html", error=error, next_url=next_url)

@app.route("/logout")
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

# -------- Account settings (unchanged core behavior) --------
@app.route("/account/settings", methods=["GET", "POST"])
def account_settings():
    if 'user_id' not in session:
        flash("Please log in to access account settings.", "warning")
        return redirect(url_for("login"))
    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None); session.pop('user_name', None)
        flash("User not found. Please sign in again.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        form = request.form
        errors = []
        email = (form.get("email") or "").strip().lower()
        address = (form.get("address") or "").strip()
        phone_number_raw = (form.get("phone_number") or "").strip()

        phone_number = None
        if phone_number_raw:
            if not phone_number_raw.isdigit():
                errors.append("Phone number must contain only numbers.")
            elif len(phone_number_raw) != 10:
                errors.append("Phone number must be exactly 10 digits.")
            else:
                phone_number = int(phone_number_raw)
        else:
            errors.append("Phone number is required.")

        credit_card_number = (form.get("credit_card_number") or "").strip()
        credit_card_name = (form.get("credit_card_name") or "").strip()
        credit_card_expiration = (form.get("credit_card_expiration") or "").strip()
        remove_credit_card = form.get("remove_credit_card") == "on"

        checking_account_number = (form.get("checking_account_number") or "").strip()
        checking_account_name = (form.get("checking_account_name") or "").strip()
        checking_routing_number_raw = (form.get("checking_routing_number") or "").strip()
        remove_checking_account = form.get("remove_checking_account") == "on"

        if checking_routing_number_raw and not checking_routing_number_raw.isdigit():
            errors.append("Routing number must contain only numbers.")

        if not email:
            errors.append("Email is required.")
        elif email != (user.email or ""):
            existing_user = User.query.filter(User.email == email, User.id != user.id).first()
            if existing_user:
                errors.append("That email address is already in use.")

        if not address:
            errors.append("Address is required.")

        new_credit_last4 = user.credit_card_last4
        new_credit_name = user.credit_card_name
        new_credit_expiration = user.credit_card_expiration
        new_checking_last4 = user.checking_account_last4
        new_checking_name = user.checking_account_name
        new_checking_routing = user.checking_routing_number

        if remove_credit_card:
            new_credit_last4 = None; new_credit_name = None; new_credit_expiration = None
        if remove_checking_account:
            new_checking_last4 = None; new_checking_name = None; new_checking_routing = None

        if credit_card_number:
            digits_only = ''.join(ch for ch in credit_card_number if ch.isdigit())
            if len(digits_only) < 4:
                errors.append("Credit card number must include at least four digits.")
            else:
                new_credit_last4 = int(digits_only[-4:])
                new_credit_name = credit_card_name or user.full_name
                new_credit_expiration = credit_card_expiration or None

        if checking_account_number:
            acct_digits = ''.join(ch for ch in checking_account_number if ch.isdigit())
            if len(acct_digits) < 4:
                errors.append("Checking account number must include at least four digits.")
            else:
                new_checking_last4 = int(acct_digits[-4:])
                new_checking_name = checking_account_name or user.full_name

            routing_digits = ''.join(ch for ch in checking_routing_number_raw if ch.isdigit())
            if routing_digits and len(routing_digits) != 9:
                errors.append("Routing number must be nine digits.")
            else:
                new_checking_routing = int(routing_digits) if routing_digits else None
        elif checking_routing_number_raw:
            errors.append("Provide a checking account number when supplying a routing number.")

        if not (new_credit_last4 or new_checking_last4):
            errors.append("At least one payment method (credit card or checking account) is required.")

        current_password = form.get("current_password") or ""
        new_password = form.get("new_password") or ""
        confirm_password = form.get("confirm_password") or ""
        password_change_requested = any([current_password, new_password, confirm_password])
        if password_change_requested:
            if not current_password:
                errors.append("Current password is required to change password.")
            elif not check_password_hash(user.password_hash, current_password):
                errors.append("Current password is incorrect.")
            if not new_password:
                errors.append("New password is required.")
            elif len(new_password) < 8:
                errors.append("New password must be at least eight characters long.")
            if new_password != confirm_password:
                errors.append("New password and confirmation do not match.")

        if errors:
            for msg in errors:
                flash(msg, "danger")
            return render_template("account_settings.html", user=user, form_data=form)

        user.email = email
        user.address = address
        user.phone_number = phone_number
        user.credit_card_last4 = new_credit_last4
        user.credit_card_name = new_credit_name
        user.credit_card_expiration = new_credit_expiration
        user.checking_account_last4 = new_checking_last4
        user.checking_account_name = new_checking_name
        user.checking_routing_number = new_checking_routing

        if password_change_requested:
            user.password_hash = generate_password_hash(new_password)
            flash("Password updated successfully.", "success")

        db.session.commit()
        flash("Account settings updated.", "success")
        return redirect(url_for("account_settings"))

    form_data = {
        "email": user.email or "",
        "address": user.address or "",
        "phone_number": user.phone_number or "",
        "credit_card_name": user.credit_card_name or "",
        "credit_card_expiration": user.credit_card_expiration or "",
        "checking_account_name": user.checking_account_name or "",
        "checking_routing_number": user.checking_routing_number or "",
    }
    return render_template("account_settings.html", user=user, form_data=form_data)

# -------- Portfolio (unchanged) --------
@app.route("/portfolio", methods=["GET", "POST"])
def portfolio():
    if 'user_id' not in session:
        flash("Please log in to view your portfolio.", "warning")
        return redirect(url_for("login"))

    user_id = session['user_id']
    user = User.query.get(user_id)
    if not user:
        session.pop('user_id', None); session.pop('user_name', None)
        flash("User not found. Please sign in again.", "danger")
        return redirect(url_for("login"))

    payment_options = []
    if user.credit_card_last4:
        payment_options.append({"value": "credit_card",
                                "label": f"{(user.credit_card_name or 'Credit Card')} ending in {user.credit_card_last4}"})
    if user.checking_account_last4:
        payment_options.append({"value": "checking_account",
                                "label": f"{(user.checking_account_name or 'Checking Account')} ending in {user.checking_account_last4}"})
    payment_option_lookup = {o["value"]: o["label"] for o in payment_options}

    if request.method == "POST":
        action = request.form.get("action", "add")
        if action == "delete":
            holding_id = request.form.get("holding_id")
            try:
                holding_id = int(holding_id)
            except (TypeError, ValueError):
                flash("Invalid request for sell.", "danger")
                return redirect(url_for("portfolio"))
            holding = PortfolioHolding.query.filter_by(id=holding_id, user_id=user_id).first()
            if not holding:
                flash("Stock holding not found.", "warning")
                return redirect(url_for("portfolio"))
            db.session.delete(holding); db.session.commit()
            flash(f"Sold {holding.symbol}. Deposited to your credit card or checking account.", "info")
            return redirect(url_for("portfolio"))

        if not payment_options:
            flash("Please add a payment method in Account Settings before buying.", "warning")
            return redirect(url_for("portfolio"))

        selected_payment_method = (request.form.get("payment_method") or "").strip()
        if selected_payment_method not in payment_option_lookup:
            flash("Select a saved payment method before buying.", "warning")
            return redirect(url_for("portfolio"))

        selected_payment_label = payment_option_lookup[selected_payment_method]
        symbol = (request.form.get("symbol") or "").upper().strip()
        shares = request.form.get("shares"); average_price = request.form.get("average_price")

        if not symbol or not shares or not average_price:
            flash("All fields are required to add a stock holding.", "danger")
        else:
            try:
                shares_value = float(shares); price_value = float(average_price)
                if shares_value <= 0 or price_value <= 0:
                    raise ValueError
                holding = PortfolioHolding.query.filter_by(user_id=user_id, symbol=symbol).first()
                if holding:
                    total_shares = holding.shares + shares_value
                    holding.average_price = ((holding.shares * holding.average_price) + (shares_value * price_value)) / total_shares
                    holding.shares = total_shares; holding.updated_at = datetime.utcnow()
                    flash(f"Updated stock holding for {symbol} using {selected_payment_label}.", "info")
                else:
                    holding = PortfolioHolding(user_id=user_id, symbol=symbol, shares=shares_value, average_price=price_value)
                    db.session.add(holding)
                    flash(f"Added {symbol} to your portfolio using {selected_payment_label}.", "success")
                db.session.commit()
            except ValueError:
                db.session.rollback(); flash("Shares and price must be positive numbers.", "danger")
            except Exception as e:
                db.session.rollback(); flash(f"Unable to save stock holding: {str(e)}", "danger")
        return redirect(url_for("portfolio"))

    holdings = PortfolioHolding.query.filter_by(user_id=user_id).order_by(PortfolioHolding.symbol).all()
    total_cost_basis = sum(h.shares * h.average_price for h in holdings)

    stock_lookup = {}
    if holdings:
        symbols = [h.symbol.upper() for h in holdings]
        stock_rows = StockSymbol.query.filter(StockSymbol.symbol.in_(symbols)).all()
        stock_lookup = {row.symbol.upper(): row for row in stock_rows}

    enriched_holdings = []
    total_market_value = 0; has_market_value = False
    for holding in holdings:
        stock = stock_lookup.get(holding.symbol.upper())
        current_price = stock.lastsale if stock and stock.lastsale is not None else None
        current_value = holding.shares * current_price if current_price is not None else None
        if current_value is not None:
            total_market_value += current_value; has_market_value = True
        enriched_holdings.append({
            "holding": holding, "stock": stock, "current_price": current_price,
            "current_value": current_value, "pct_change": stock.pctchange if stock else None,
            "market": stock.market if stock else None,
        })

    total_market_value = total_market_value if has_market_value else None
    unrealized_pl = (total_market_value - total_cost_basis) if total_market_value is not None else None

    return render_template("portfolio.html",
                           holdings=enriched_holdings,
                           total_cost_basis=total_cost_basis,
                           total_market_value=total_market_value,
                           unrealized_pl=unrealized_pl,
                           payment_options=payment_options)

# -------- API --------
@app.route("/api/symbols")
def api_symbols():
    query = (request.args.get("q") or "").upper().strip()
    limit = min(request.args.get("limit", default=20, type=int), 50)
    if not query:
        return jsonify([])
    results = (StockSymbol.query
               .filter(StockSymbol.symbol.like(f"{query}%"))
               .order_by(StockSymbol.symbol)
               .limit(limit).all())
    payload = [{"symbol": s.symbol, "name": s.name, "market": s.market, "lastsale": s.lastsale} for s in results]
    return jsonify(payload)

# -------- Signup (no auto-login) --------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if not full_name or not email or not password:
            flash("Full name, email, and password are required.", "danger")
            return redirect(url_for("signup"))

        if User.query.filter_by(email=email).first():
            flash("That email is already registered. Try logging in.", "warning")
            return redirect(url_for("login"))
        try:
            password_hash = generate_password_hash(password)
            db.session.add(User(full_name=full_name, email=email, password_hash=password_hash))
            db.session.commit()
            flash("Account created successfully! Please sign in.", "success")
            return redirect(url_for("login"))
        except IntegrityError:
            db.session.rollback()
            flash("That email is already registered. Try logging in.", "warning")
            return redirect(url_for("login"))
        except Exception as e:
            db.session.rollback()
            flash(f"Could not create account: {e}", "danger")
            return redirect(url_for("signup"))
    return render_template("signup.html")

# -------- Startup --------
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
