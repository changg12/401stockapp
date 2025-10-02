from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session
from datetime import datetime
from math import ceil
from sqlalchemy import func

app = Flask(__name__)
bootstrap = Bootstrap(app)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:password@localhost/flask_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'awdasdawdasdawdasdawdasd'

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    phone_number = db.Column(db.String(20))
    address = db.Column(db.String(255))
    credit_card_name = db.Column(db.String(100))
    credit_card_last4 = db.Column(db.String(4))
    credit_card_expiration = db.Column(db.String(7))
    checking_account_name = db.Column(db.String(100))
    checking_account_last4 = db.Column(db.String(4))
    checking_routing_number = db.Column(db.String(9))
    created_at = db.Column(db.DateTime, server_default=db.func.now())



class SavedPaymentInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    username = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    address = db.Column(db.String(255), nullable=False)
    address2 = db.Column(db.String(255), nullable=True)
    country = db.Column(db.String(50), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    
    
    payment_method = db.Column(db.String(20), nullable=False)  
    card_name = db.Column(db.String(100), nullable=True)
    card_number_last4 = db.Column(db.String(4), nullable=True)  
    card_expiration = db.Column(db.String(7), nullable=True)  
    
    
    same_address = db.Column(db.Boolean, default=False)
    
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    
    __table_args__ = (db.UniqueConstraint('user_id', name='unique_user_saved_payment'),)


class PortfolioHolding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    shares = db.Column(db.Float, nullable=False)
    average_price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'symbol', name='unique_symbol_per_user'),
    )

# Stock symbols data from https://github.com/rreichel3/US-Stock-Symbols/tree/main
# Please use your own database and import the flask_db_stock_symbols.sql file for testing
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

        avg_value = sum_value / count_value if count_value else 0
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
        total_pages = max(ceil(total_items / per_page), 1) if total_items else 1

        if page < 1:
            page = 1
        elif page > total_pages:
            page = total_pages

        symbols = (
            base_query
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        def build_page_items(current_page, total_pages_count):
            if total_pages_count <= 7:
                return [
                    {"number": num, "ellipsis": False}
                    for num in range(1, total_pages_count + 1)
                ]

            items = []

            def add_number(num):
                if not any(entry.get("number") == num for entry in items):
                    items.append({"number": num, "ellipsis": False})

            add_number(1)

            if current_page > 4:
                items.append({"number": None, "ellipsis": True})

            for num in range(current_page - 1, current_page + 2):
                if 1 < num < total_pages_count:
                    add_number(num)

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
                url = url_for("home", **args)
                pagination_links.append(
                    {
                        "label": str(item["number"]),
                        "url": url,
                        "active": item["number"] == page,
                        "disabled": False,
                    }
                )

        prev_args = existing_args.copy()
        prev_args[param_name] = max(page - 1, 1)
        next_args = existing_args.copy()
        next_args[param_name] = min(page + 1, total_pages)

        market_pagination[market] = {
            "page": page,
            "total_pages": total_pages,
            "total_items": total_items,
            "per_page": per_page,
            "prev_url": url_for("home", **prev_args),
            "next_url": url_for("home", **next_args),
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "links": pagination_links,
            "param_name": param_name,
        }

        stocks_by_market[market] = symbols

    return render_template(
        "stock.html",
        markets=markets,
        avg_pct_change=avg_pct_change,
        stocks_by_market=stocks_by_market,
        market_pagination=market_pagination,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['user_name'] = user.full_name 
            flash("Login successful!", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid email or password", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    flash("You have been logged out.", "info")
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

    if request.method == "POST":
        form = request.form
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

        if password_change_requested and not errors:
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




@app.route("/orders", methods=["GET", "POST"])
def orders():
    if request.method == "POST":
        try:
            
            save_info = 'save-info' in request.form
            
            
            user_id = session.get('user_id')
            
            
            if user_id and save_info:
                
                first_name = request.form.get('firstName')
                last_name = request.form.get('lastName')
                username = request.form.get('username')
                email = request.form.get('email')
                address = request.form.get('address')
                address2 = request.form.get('address2')
                country = request.form.get('country')
                state = request.form.get('state')
                zip_code = request.form.get('zip')
                payment_method = request.form.get('paymentMethod')
                card_name = request.form.get('cc-name')
                card_number = request.form.get('cc-number')
                card_expiration = request.form.get('cc-expiration')
                card_number_last4 = card_number[-4:] if card_number else None
                same_address = 'same-address' in request.form
                
                
                existing_saved_info = SavedPaymentInfo.query.filter_by(user_id=user_id).first()
                
                if existing_saved_info:
                    
                    existing_saved_info.first_name = first_name
                    existing_saved_info.last_name = last_name
                    existing_saved_info.username = username
                    existing_saved_info.email = email
                    existing_saved_info.address = address
                    existing_saved_info.address2 = address2
                    existing_saved_info.country = country
                    existing_saved_info.state = state
                    existing_saved_info.zip_code = zip_code
                    existing_saved_info.payment_method = payment_method
                    existing_saved_info.card_name = card_name
                    existing_saved_info.card_number_last4 = card_number_last4
                    existing_saved_info.card_expiration = card_expiration
                    existing_saved_info.same_address = same_address
                    existing_saved_info.updated_at = datetime.utcnow()
                    flash("Payment information updated successfully!", "info")
                else:
                    
                    saved_payment_info = SavedPaymentInfo(
                        user_id=user_id,
                        first_name=first_name,
                        last_name=last_name,
                        username=username,
                        email=email,
                        address=address,
                        address2=address2,
                        country=country,
                        state=state,
                        zip_code=zip_code,
                        payment_method=payment_method,
                        card_name=card_name,
                        card_number_last4=card_number_last4,
                        card_expiration=card_expiration,
                        same_address=same_address
                    )
                    db.session.add(saved_payment_info)
                    flash("Payment information saved for next time!", "success")
                
                db.session.commit()
            
            
            
            flash("Order placed successfully!", "success")
            return redirect(url_for("home"))

        except Exception as e:
            db.session.rollback()
            flash(f"Error processing order: {str(e)}", "danger")
            return redirect(url_for("orders"))
    
    else:  
        saved_info = None
        if 'user_id' in session:
            saved_info = SavedPaymentInfo.query.filter_by(user_id=session['user_id']).first()
        
        return render_template("cart.html", saved_info=saved_info)

# Portfolio management routes - by Kadir Karabulut
@app.route("/portfolio", methods=["GET", "POST"])
def portfolio():
    if 'user_id' not in session:
        flash("Please log in to view your portfolio.", "warning")
        return redirect(url_for("login"))

    user_id = session['user_id']
    user = User.query.get(user_id)

    if not user:
        session.pop('user_id', None)
        session.pop('user_name', None)
        flash("User not found. Please sign in again.", "danger")
        return redirect(url_for("login"))

    payment_options = []

    if user.credit_card_last4:
        card_name = user.credit_card_name or "Credit Card"
        payment_options.append({
            "value": "credit_card",
            "label": f"{card_name} ending in {user.credit_card_last4}",
        })

    if user.checking_account_last4:
        account_name = user.checking_account_name or "Checking Account"
        payment_options.append({
            "value": "checking_account",
            "label": f"{account_name} ending in {user.checking_account_last4}",
        })

    payment_option_lookup = {option["value"]: option["label"] for option in payment_options}

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

            db.session.delete(holding)
            db.session.commit()
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
        shares = request.form.get("shares")
        average_price = request.form.get("average_price")

        if not symbol or not shares or not average_price:
            flash("All fields are required to add a stock holding.", "danger")
        else:
            try:
                shares_value = float(shares)
                price_value = float(average_price)

                if shares_value <= 0 or price_value <= 0:
                    raise ValueError

                holding = PortfolioHolding.query.filter_by(user_id=user_id, symbol=symbol).first()

                if holding:
                    total_shares = holding.shares + shares_value
                    holding.average_price = (
                        (holding.shares * holding.average_price) + (shares_value * price_value)
                    ) / total_shares
                    holding.shares = total_shares
                    holding.updated_at = datetime.utcnow()
                    flash(f"Updated stock holding for {symbol} using {selected_payment_label}.", "info")
                else:
                    holding = PortfolioHolding(
                        user_id=user_id,
                        symbol=symbol,
                        shares=shares_value,
                        average_price=price_value,
                    )
                    db.session.add(holding)
                    flash(f"Added {symbol} to your portfolio using {selected_payment_label}.", "success")

                db.session.commit()
            except ValueError:
                db.session.rollback()
                flash("Shares and price must be positive numbers.", "danger")
            except Exception as e:
                db.session.rollback()
                flash(f"Unable to save stock holding: {str(e)}", "danger")

        return redirect(url_for("portfolio"))

    holdings = (
        PortfolioHolding.query
        .filter_by(user_id=user_id)
        .order_by(PortfolioHolding.symbol)
        .all()
    )

    total_cost_basis = sum(h.shares * h.average_price for h in holdings)

    stock_lookup = {}
    if holdings:
        symbols = [h.symbol.upper() for h in holdings]
        stock_rows = (
            StockSymbol.query
            .filter(StockSymbol.symbol.in_(symbols))
            .all()
        )
        stock_lookup = {row.symbol.upper(): row for row in stock_rows}

    enriched_holdings = []
    total_market_value = 0
    has_market_value = False

    for holding in holdings:
        stock = stock_lookup.get(holding.symbol.upper())
        current_price = stock.lastsale if stock and stock.lastsale is not None else None
        current_value = holding.shares * current_price if current_price is not None else None
        if current_value is not None:
            total_market_value += current_value
            has_market_value = True

        enriched_holdings.append(
            {
                "holding": holding,
                "stock": stock,
                "current_price": current_price,
                "current_value": current_value,
                "pct_change": stock.pctchange if stock else None,
                "market": stock.market if stock else None,
            }
        )

    total_market_value = total_market_value if has_market_value else None
    unrealized_pl = (
        total_market_value - total_cost_basis
        if total_market_value is not None
        else None
    )

    return render_template(
        "portfolio.html",
        holdings=enriched_holdings,
        total_cost_basis=total_cost_basis,
        total_market_value=total_market_value,
        unrealized_pl=unrealized_pl,
        payment_options=payment_options,
    )
# End of portfolio management routes


@app.route("/api/symbols")
def api_symbols():
    query = (request.args.get("q") or "").upper().strip()
    limit = min(request.args.get("limit", default=20, type=int), 50)

    if not query:
        return jsonify([])

    results = (
        StockSymbol.query
        .filter(StockSymbol.symbol.like(f"{query}%"))
        .order_by(StockSymbol.symbol)
        .limit(limit)
        .all()
    )

    payload = [
        {
            "symbol": stock.symbol,
            "name": stock.name,
            "market": stock.market,
            "lastsale": stock.lastsale,
        }
        for stock in results
    ]

    return jsonify(payload)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        password = request.form.get("password")

        password_hash = generate_password_hash(password)

        new_user = User(full_name=full_name, email=email, password_hash=password_hash)
        db.session.add(new_user)
        db.session.commit()

        flash("Account created successfully!", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
