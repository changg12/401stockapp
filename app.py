from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, time
import pytz

app = Flask(__name__)
<<<<<<< Updated upstream
=======
bootstrap = Bootstrap(app)

# Database configuration
>>>>>>> Stashed changes
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:password@localhost/flask_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'awdasdawdasdawdasdawdasd'

db = SQLAlchemy(app)
Bootstrap(app)

MARKET_TZ = pytz.timezone("America/New_York")
DEFAULT_MARKET_OPEN_TIME = time(9, 30)
DEFAULT_MARKET_CLOSE_TIME = time(16, 0)

# --------------------- MODELS ---------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    phone_number = db.Column(db.String(15))
    address = db.Column(db.String(255))
    credit_card_last4 = db.Column(db.String(4))
    checking_account_last4 = db.Column(db.String(4))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PortfolioHolding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    symbol = db.Column(db.String(10))
    shares = db.Column(db.Float)
    average_price = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class Transactions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    symbol = db.Column(db.String(10))
    transaction_type = db.Column(db.String(10))
    shares = db.Column(db.Float)
    price = db.Column(db.Float)
    total_amount = db.Column(db.Float)
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)

class StockSymbols(db.Model):
    symbol = db.Column(db.String(10), primary_key=True)
    market = db.Column(db.String(50))
    name = db.Column(db.String(100))
    lastsale = db.Column(db.Float)
    netchange = db.Column(db.Float)
    pctchange = db.Column(db.Float)
    volume = db.Column(db.BigInteger)
    marketCap = db.Column(db.BigInteger)
    country = db.Column(db.String(50))
    industry = db.Column(db.String(100))
    sector = db.Column(db.String(100))

# --------------------- HELPERS ---------------------
def is_logged_in():
    return session.get("user_id") is not None

def is_market_open():
    now = datetime.now(MARKET_TZ).time()
    return DEFAULT_MARKET_OPEN_TIME <= now <= DEFAULT_MARKET_CLOSE_TIME

# --------------------- ROUTES ---------------------
@app.route('/')
def home():
    redirect_after = request.args.get('redirect_after', False)
    stocks = StockSymbols.query.limit(50).all()
    return render_template('stock.html', stocks=stocks, markets=[], stocks_by_market={}, market_pagination={}, avg_pct_change=[], redirect_after=redirect_after)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']
        confirm = request.form['confirm_password']

        if password != confirm:
            flash("Passwords do not match", "danger")
            return render_template('signup.html')

        # Create and save the new user
        user = User(full_name=full_name, email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()

        # Log in the user immediately
        session['user_id'] = user.id
        session['full_name'] = user.full_name

        flash("Signup successful", "success")
        return redirect(url_for('home', redirect_after=True))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if is_logged_in():
        return redirect(url_for('home'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['full_name'] = user.full_name
            flash("Login successful", "success")
            return redirect(url_for('home', redirect_after=True))

        flash("Incorrect email or password", "danger")

<<<<<<< Updated upstream
    return render_template('login.html')
=======
            flash("Login successful!", "success")
            return render_template("login.html", redirect_to_home=True)
        else:
            flash("Invalid email or password", "danger")
            return render_template("login.html", redirect_to_home=False)
>>>>>>> Stashed changes

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

<<<<<<< Updated upstream
@app.route('/portfolio')
=======
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('is_admin', None)
    return redirect(url_for("home"))



@app.route("/account/settings", methods=["GET", "POST"])
def account_settings():
    if 'user_id' not in session:
        flash("Please log in to access account settings.", "warning")
        return redirect(url_for("login"))

    user = User.query.get(session['user_id'])

    if not user:
        session.pop('user_id', None)
        session.pop('user_name', None)
        flash("User not found. Please sign in again.", "danger")
        return redirect(url_for("login"))

    active_tab = request.args.get("tab") or (request.form.get("tab") if request.method == "POST" else None) or "profile"

    payment_methods = []
    if user.credit_card_last4:
        payment_methods.append({
            "value": "credit_card",
            "label": f"Credit Card ending in {user.credit_card_last4}",
        })
    if user.checking_account_last4:
        payment_methods.append({
            "value": "checking_account",
            "label": f"Checking Account ending in {user.checking_account_last4}",
        })

    if request.method == "POST":
        form_type = request.form.get("form_type", "profile")
        if form_type == "wallet":
            amount_raw = (request.form.get("wallet_amount") or "").strip()
            action = request.form.get("wallet_action")
            payment_source = request.form.get("wallet_payment_source")

            errors = []

            try:
                amount_value = float(amount_raw)
            except ValueError:
                amount_value = None

            if amount_value is None or amount_value <= 0:
                errors.append("Enter a positive amount to process.")

            if payment_source not in {method["value"] for method in payment_methods}:
                errors.append("Select a valid funding source.")

            if action not in {"deposit", "withdraw"}:
                errors.append("Choose whether to deposit or withdraw.")

            if not errors and action == "withdraw" and amount_value > user.wallet_balance:
                errors.append("Insufficient wallet balance for withdrawal.")

            if errors:
                for message in errors:
                    flash(message, "danger")
                return render_template(
                    "account_settings.html",
                    user=user,
                    form_data={
                        "email": user.email or "",
                        "address": user.address or "",
                        "phone_number": user.phone_number or "",
                        "credit_card_name": user.credit_card_name or "",
                        "credit_card_expiration": user.credit_card_expiration or "",
                        "checking_account_name": user.checking_account_name or "",
                        "checking_routing_number": user.checking_routing_number or "",
                    },
                    active_tab="wallet",
                    payment_methods=payment_methods,
                    wallet_balance=user.wallet_balance,
                )

            if action == "deposit":
                user.wallet_balance += amount_value
                flash(f"Deposited ${amount_value:.2f} into wallet.", "success")
            else:
                user.wallet_balance -= amount_value
                flash(f"Withdrew ${amount_value:.2f} from wallet.", "success")

            db.session.commit()
            return redirect(url_for("account_settings", tab="wallet"))

        form = request.form
        active_tab = "profile"
        email = (form.get("email") or "").strip()
        address = (form.get("address") or "").strip()
        phone_number = (form.get("phone_number") or "").strip()

        credit_card_number = (form.get("credit_card_number") or "").strip()
        credit_card_name = (form.get("credit_card_name") or "").strip()
        credit_card_expiration = (form.get("credit_card_expiration") or "").strip()
        remove_credit_card = form.get("remove_credit_card") == "on"

        checking_account_number = (form.get("checking_account_number") or "").strip()
        checking_account_name = (form.get("checking_account_name") or "").strip()
        checking_routing_number = (form.get("checking_routing_number") or "").strip()
        remove_checking_account = form.get("remove_checking_account") == "on"

        current_password = form.get("current_password") or ""
        new_password = form.get("new_password") or ""
        confirm_password = form.get("confirm_password") or ""

        errors = []

        if not email:
            errors.append("Email is required.")

        if email and email != user.email:
            existing_user = User.query.filter(User.email == email, User.id != user.id).first()
            if existing_user:
                errors.append("That email address is already in use.")

        if not address:
            errors.append("Address is required.")

        if not phone_number:
            errors.append("Phone number is required.")

        # Prepare payment data updates
        new_credit_last4 = user.credit_card_last4
        new_credit_name = user.credit_card_name
        new_credit_expiration = user.credit_card_expiration

        new_checking_last4 = user.checking_account_last4
        new_checking_name = user.checking_account_name
        new_checking_routing = user.checking_routing_number

        if remove_credit_card:
            new_credit_last4 = None
            new_credit_name = None
            new_credit_expiration = None

        if remove_checking_account:
            new_checking_last4 = None
            new_checking_name = None
            new_checking_routing = None

        if credit_card_number:
            digits_only = ''.join(ch for ch in credit_card_number if ch.isdigit())
            if len(digits_only) < 4:
                errors.append("Credit card number must include at least four digits.")
            else:
                new_credit_last4 = digits_only[-4:]
                new_credit_name = credit_card_name or user.full_name
                new_credit_expiration = credit_card_expiration or None

        if checking_account_number:
            acct_digits = ''.join(ch for ch in checking_account_number if ch.isdigit())
            if len(acct_digits) < 4:
                errors.append("Checking account number must include at least four digits.")
            else:
                new_checking_last4 = acct_digits[-4:]
                new_checking_name = checking_account_name or user.full_name

            routing_digits = ''.join(ch for ch in checking_routing_number if ch.isdigit())
            if routing_digits and len(routing_digits) != 9:
                errors.append("Routing number must be nine digits.")
            else:
                new_checking_routing = routing_digits or None
        elif checking_routing_number:
            # Routing number without account doesn't make sense
            errors.append("Provide a checking account number when supplying a routing number.")

        if not (new_credit_last4 or new_checking_last4):
            errors.append("At least one payment method (credit card or checking account) is required.")

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
            for message in errors:
                flash(message, "danger")
            return render_template(
                "account_settings.html",
                user=user,
                form_data=form,
                active_tab="profile",
                payment_methods=payment_methods,
                wallet_balance=user.wallet_balance,
            )

        user.email = email
        user.address = address
        user.phone_number = phone_number
        user.credit_card_last4 = new_credit_last4
        user.credit_card_name = new_credit_name
        user.credit_card_expiration = new_credit_expiration
        user.checking_account_last4 = new_checking_last4
        user.checking_account_name = new_checking_name
        user.checking_routing_number = new_checking_routing

        if password_change_requested and not errors:
            user.password_hash = generate_password_hash(new_password)
            flash("Password updated successfully.", "success")

        db.session.commit()

        flash("Account settings updated.", "success")
        return redirect(url_for("account_settings", tab="profile"))

    form_data = {
        "email": user.email or "",
        "address": user.address or "",
        "phone_number": user.phone_number or "",
        "credit_card_name": user.credit_card_name or "",
        "credit_card_expiration": user.credit_card_expiration or "",
        "checking_account_name": user.checking_account_name or "",
        "checking_routing_number": user.checking_routing_number or "",
    }

    return render_template(
        "account_settings.html",
        user=user,
        form_data=form_data,
        active_tab=active_tab,
        payment_methods=payment_methods,
        wallet_balance=user.wallet_balance,
    )

@app.route("/admin", methods=["GET", "POST"])
def admin_portal():
    allowed, admin_user = require_admin_access()
    if not allowed:
        return admin_user

    active_tab = request.args.get("tab") or request.form.get("tab") or "users"

    if request.method == "POST":
        form_tab = request.form.get("tab", "users")
        active_tab = form_tab

        if form_tab == "users":
            try:
                target_user_id = int(request.form.get("user_id"))
            except (TypeError, ValueError):
                flash("Invalid user selection.", "danger")
                return redirect(url_for("admin_portal", tab=form_tab))

            target_user = User.query.get(target_user_id)
            if not target_user:
                flash("Selected user not found.", "danger")
                return redirect(url_for("admin_portal", tab=form_tab))

            new_first_name = (request.form.get("first_name") or "").strip()
            new_last_name = (request.form.get("last_name") or "").strip()
            new_email = (request.form.get("email") or "").strip().lower()
            new_password = (request.form.get("new_password") or "").strip()
            wants_admin = request.form.get("is_admin") == "on"

            if not new_email:
                flash("Email address is required.", "warning")
                return redirect(url_for("admin_portal", tab=form_tab))

            existing_email_user = User.query.filter(User.email == new_email, User.id != target_user.id).first()
            if existing_email_user:
                flash("Another account already uses that email address.", "warning")
                return redirect(url_for("admin_portal", tab=form_tab))

            if target_user.id == admin_user.id and not wants_admin:
                flash("You cannot remove your own administrator rights while signed in.", "warning")
                return redirect(url_for("admin_portal", tab=form_tab))

            target_user.first_name = new_first_name or None
            target_user.last_name = new_last_name or None
            target_user.email = new_email
            target_user.is_admin = wants_admin

            new_full_name = f"{new_first_name} {new_last_name}".strip()
            if new_full_name:
                target_user.full_name = new_full_name
            else:
                target_user.full_name = new_email

            if new_password:
                target_user.password_hash = generate_password_hash(new_password)

            db.session.commit()

            if target_user.id == admin_user.id:
                session['user_name'] = target_user.full_name
                session['is_admin'] = bool(target_user.is_admin)

            flash("User details updated successfully.", "success")
            return redirect(url_for("admin_portal", tab=form_tab))

        elif form_tab == "market":
            action = request.form.get("action", "save_override")

            if action == "delete_override":
                try:
                    override_id = int(request.form.get("override_id"))
                except (TypeError, ValueError):
                    flash("Could not determine which override to delete.", "danger")
                    return redirect(url_for("admin_portal", tab=form_tab))

                override = MarketScheduleOverride.query.get(override_id)
                if not override:
                    flash("Override not found.", "warning")
                    return redirect(url_for("admin_portal", tab=form_tab))

                db.session.delete(override)
                db.session.commit()
                flash("Market schedule override removed.", "success")
                return redirect(url_for("admin_portal", tab=form_tab))

            # Save or update override
            raw_date = (request.form.get("override_date") or "").strip()
            if not raw_date:
                flash("Please provide a date for the market schedule override.", "warning")
                return redirect(url_for("admin_portal", tab=form_tab))

            try:
                override_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
            except ValueError:
                flash("Invalid date format. Please use YYYY-MM-DD.", "danger")
                return redirect(url_for("admin_portal", tab=form_tab))

            is_closed = request.form.get("is_closed") == "on"
            open_time_value = None
            close_time_value = None

            if not is_closed:
                open_time_str = (request.form.get("open_time") or "").strip()
                close_time_str = (request.form.get("close_time") or "").strip()

                if not open_time_str or not close_time_str:
                    flash("Provide both an open and close time or mark the market as closed.", "warning")
                    return redirect(url_for("admin_portal", tab=form_tab))

                try:
                    open_time_value = datetime.strptime(open_time_str, "%H:%M").time()
                    close_time_value = datetime.strptime(close_time_str, "%H:%M").time()
                except ValueError:
                    flash("Invalid time format. Use HH:MM in 24-hour time.", "danger")
                    return redirect(url_for("admin_portal", tab=form_tab))

                if close_time_value <= open_time_value:
                    flash("Close time must be after open time.", "warning")
                    return redirect(url_for("admin_portal", tab=form_tab))

            note = (request.form.get("note") or "").strip() or None

            override = MarketScheduleOverride.query.filter_by(date=override_date).first()
            if override:
                override.is_closed = is_closed
                override.open_time = open_time_value
                override.close_time = close_time_value
                override.note = note
            else:
                override = MarketScheduleOverride(
                    date=override_date,
                    is_closed=is_closed,
                    open_time=open_time_value,
                    close_time=close_time_value,
                    note=note,
                )
                db.session.add(override)

            db.session.commit()

            flash("Market schedule override saved.", "success")
            return redirect(url_for("admin_portal", tab=form_tab))

        elif form_tab == "stocks":
            action = request.form.get("action", "")

            def parse_float(value, field_label, required=False):
                if value is None:
                    value = ""
                value = value.strip()
                if not value:
                    if required:
                        raise ValueError(f"{field_label} is required.")
                    return None
                try:
                    return float(value)
                except ValueError:
                    raise ValueError(f"{field_label} must be a valid number.")

            if action == "create_stock":
                market = (request.form.get("market") or "").strip().upper()
                symbol = (request.form.get("symbol") or "").strip().upper()
                name = (request.form.get("name") or "").strip()

                if not market:
                    flash("Market is required to create a stock.", "warning")
                    return redirect(url_for("admin_portal", tab=form_tab))

                if not symbol:
                    flash("Stock symbol is required.", "warning")
                    return redirect(url_for("admin_portal", tab=form_tab))

                if not name:
                    flash("Company name is required.", "warning")
                    return redirect(url_for("admin_portal", tab=form_tab))

                try:
                    lastsale_value = parse_float(request.form.get("lastsale"), "Last sale price", required=True)
                    volume_value = parse_float(request.form.get("volume"), "Volume", required=False)
                    market_cap_value = parse_float(request.form.get("marketCap"), "Market cap", required=False)
                except ValueError as exc:
                    flash(str(exc), "warning")
                    return redirect(url_for("admin_portal", tab=form_tab))

                existing_stock = (
                    StockSymbol.query
                    .filter(func.upper(StockSymbol.symbol) == symbol)
                    .first()
                )
                if existing_stock:
                    flash("A stock with that symbol already exists in the system.", "warning")
                    return redirect(url_for("admin_portal", tab=form_tab, stock_symbol=symbol))

                new_stock = StockSymbol(
                    market=market,
                    symbol=symbol,
                    name=name,
                    lastsale=lastsale_value,
                    volume=volume_value,
                    market_cap=market_cap_value,
                    country=(request.form.get("country") or "").strip() or None,
                    industry=(request.form.get("industry") or "").strip() or None,
                    sector=(request.form.get("sector") or "").strip() or None,
                    createdate=datetime.utcnow(),
                )

                try:
                    db.session.add(new_stock)
                    db.session.commit()
                    flash(f"Stock {symbol} created successfully.", "success")
                except Exception as exc:
                    db.session.rollback()
                    flash(f"Unable to create stock: {exc}", "danger")
                    return redirect(url_for("admin_portal", tab=form_tab))

                return redirect(url_for("admin_portal", tab=form_tab, stock_symbol=symbol))

            elif action == "update_stock":
                original_symbol = (request.form.get("original_symbol") or "").strip().upper()
                original_market = (request.form.get("original_market") or "").strip().upper()

                if not original_symbol or not original_market:
                    flash("Missing original stock identifiers.", "warning")
                    return redirect(url_for("admin_portal", tab=form_tab))

                stock = StockSymbol.query.filter_by(market=original_market, symbol=original_symbol).first()
                if not stock:
                    flash("Could not find the stock to update.", "danger")
                    return redirect(url_for("admin_portal", tab=form_tab))

                market = (request.form.get("market") or "").strip().upper()
                symbol = (request.form.get("symbol") or "").strip().upper()
                name = (request.form.get("name") or "").strip()

                if not market:
                    flash("Market is required.", "warning")
                    return redirect(url_for("admin_portal", tab=form_tab, stock_symbol=original_symbol))

                if not symbol:
                    flash("Stock symbol is required.", "warning")
                    return redirect(url_for("admin_portal", tab=form_tab, stock_symbol=original_symbol))

                if not name:
                    flash("Company name is required.", "warning")
                    return redirect(url_for("admin_portal", tab=form_tab, stock_symbol=original_symbol))

                try:
                    lastsale_value = parse_float(request.form.get("lastsale"), "Last sale price", required=True)
                    volume_value = parse_float(request.form.get("volume"), "Volume", required=False)
                    market_cap_value = parse_float(request.form.get("marketCap"), "Market cap", required=False)
                except ValueError as exc:
                    flash(str(exc), "warning")
                    return redirect(url_for("admin_portal", tab=form_tab, stock_symbol=original_symbol))

                if (market != original_market) or (symbol != original_symbol):
                    existing_target = (
                        StockSymbol.query
                        .filter(func.upper(StockSymbol.symbol) == symbol)
                        .first()
                    )
                    if existing_target and not (
                        existing_target.market == original_market
                        and existing_target.symbol.upper() == original_symbol
                    ):
                        flash("Another stock already uses that symbol.", "warning")
                        return redirect(url_for("admin_portal", tab=form_tab, stock_symbol=original_symbol))

                stock.market = market
                stock.symbol = symbol
                stock.name = name
                stock.lastsale = lastsale_value
                stock.volume = volume_value
                stock.market_cap = market_cap_value
                stock.country = (request.form.get("country") or "").strip() or None
                stock.industry = (request.form.get("industry") or "").strip() or None
                stock.sector = (request.form.get("sector") or "").strip() or None

                try:
                    db.session.commit()
                    flash(f"Stock {symbol} updated successfully.", "success")
                except Exception as exc:
                    db.session.rollback()
                    flash(f"Unable to update stock: {exc}", "danger")
                    return redirect(url_for("admin_portal", tab=form_tab, stock_symbol=original_symbol))

                return redirect(url_for("admin_portal", tab=form_tab, stock_symbol=symbol))

            else:
                flash("Unsupported stock action.", "warning")
                return redirect(url_for("admin_portal", tab="stocks"))

        else:
            flash("Unsupported admin action.", "warning")
            return redirect(url_for("admin_portal", tab="users"))

    users = User.query.order_by(User.full_name.asc()).all()
    admin_logs = (
        db.session.query(User.full_name, UserLoginLog.login_at, UserLoginLog.logout_at)
        .join(User, User.id == UserLoginLog.user_id)
        .filter(User.is_admin.is_(True))
        .order_by(UserLoginLog.login_at.desc())
        .all()
    )

    market_overrides = (
        MarketScheduleOverride.query
        .order_by(MarketScheduleOverride.date.asc())
        .all()
    )

    today_status = get_market_status()
    default_open_label = DEFAULT_MARKET_OPEN_TIME.strftime("%I:%M %p").lstrip("0")
    default_close_label = DEFAULT_MARKET_CLOSE_TIME.strftime("%I:%M %p").lstrip("0")

    stock_to_edit = None
    stock_search_symbol = None
    if active_tab == "stocks":
        symbol_query = (request.args.get("stock_symbol") or "").strip()
        if symbol_query:
            stock_search_symbol = symbol_query.upper()
            stock_to_edit = (
                StockSymbol.query
                .filter(func.upper(StockSymbol.symbol) == stock_search_symbol)
                .order_by(StockSymbol.market.asc())
                .first()
            )
            if not stock_to_edit:
                flash(f"No stock found with symbol {stock_search_symbol}.", "info")

    return render_template(
        "admin.html",
        users=users,
        admin_logs=admin_logs,
        active_tab=active_tab,
        market_overrides=market_overrides,
        default_open_time=default_open_label,
        default_close_time=default_close_label,
        market_status_summary=today_status,
        stock_to_edit=stock_to_edit,
        stock_search_symbol=stock_search_symbol,
    )


@app.route("/admin/customers")
def admin_customers():
    allowed, _ = require_admin_access()
    if not allowed:
        return _

    activity_rows = build_customer_activity_summary()
    return render_template("admin_customers.html", customer_activity=activity_rows)


# Portfolio management routes - by Kadir Karabulut
@app.route("/portfolio", methods=["GET", "POST"])
>>>>>>> Stashed changes
def portfolio():
    if not is_logged_in():
        return redirect(url_for('login'))

    user_id = session['user_id']
    holdings = PortfolioHolding.query.filter_by(user_id=user_id).all()
    data = []
    total_cost_basis = 0
    total_market_value = 0

    for h in holdings:
        stock = StockSymbols.query.get(h.symbol)
        current_price = stock.lastsale if stock else 0
        cost_value = h.shares * h.average_price
        curr_value = h.shares * current_price

        total_cost_basis += cost_value
        total_market_value += curr_value

        data.append({
            "holding": h,
            "stock": stock,
            "cost_value": cost_value,
            "current_price": current_price,
            "current_value": curr_value,
            "pct_change": stock.pctchange if stock else None,
            "market": stock.market if stock else None
        })

    unrealized_pl = total_market_value - total_cost_basis
    return render_template('portfolio.html',
        holdings=data,
        total_cost_basis=total_cost_basis,
        total_market_value=total_market_value,
        unrealized_pl=unrealized_pl,
        wallet_balance=0,
        ipo_stocks=[],
        market_open=is_market_open(),
        market_notice="")

@app.route('/account_settings', methods=['GET', 'POST'])
def account_settings():
    if not is_logged_in():
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    tab = request.args.get('tab', 'profile')

    form_data = {}
    payment_methods = []
    wallet_balance = 0

    if request.method == 'POST':
        tab = request.form.get('tab', 'profile')
        form_type = request.form.get('form_type')

        if form_type == 'profile':
            # Logic here
            pass
        elif form_type == 'wallet':
            # Logic here
            pass

    return render_template(
        'account_settings.html',
        user=user,
        form_data=form_data,
        active_tab=tab,
        payment_methods=payment_methods,
        wallet_balance=wallet_balance
    )

@app.route('/reports')
def reports():
    if not is_logged_in():
        return redirect(url_for('login'))

    try:
        user_id = session['user_id']
        tx = Transactions.query.filter_by(user_id=user_id).all()

        transactions = [{
            "symbol": t.symbol or "",
            "transaction_type": t.transaction_type or "",
            "shares": t.shares or 0,
            "price": t.price or 0,
            "total_amount": t.total_amount or 0,
            "transaction_date": t.transaction_date or datetime.utcnow()
        } for t in tx]

        return render_template(
            'reports.html',
            transactions=transactions,
            total_cost_basis=0,
            total_market_value=0,
            total_performance=0,
            total_performance_pct=0,
            total_sell_value=0,
            realized_cost=0,
            holding_rows=[],
            performance_rows=[],
            period_definitions=[],
            portfolio_performance={}
        )
    except Exception as e:
        import traceback
        print("REPORT ERROR:", traceback.format_exc())
        flash("Failed to load reports.", "danger")
        return redirect(url_for('home'))

@app.route('/admin')
def admin():
    return render_template('admin.html', users=User.query.all())

@app.route('/admin/customers')
def admin_customers():
    return render_template('admin_customers.html', users=User.query.all())

@app.errorhandler(500)
def internal(e):
    return "<h1>500 - Internal Error</h1>", 500

@app.errorhandler(404)
def missing(e):
    return "<h1>404 - Not Found</h1>", 404

if __name__ == '__main__':
    app.run(debug=True)
