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


#User information model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())




#orders
class OrderPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    payment_type = db.Column(db.String(20), nullable=False)
    card_name = db.Column(db.String(100), nullable=True)
    card_number_last4 = db.Column(db.String(4), nullable=True)
    card_expiration = db.Column(db.String(7), nullable=True) 
    bank_account_number = db.Column(db.BigInteger, nullable=True)  
    bank_routing_number = db.Column(db.Integer, nullable=True) 
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'card_number_last4', 'bank_account_number', name='unique_user_payment'),)


# Portfolio management model - by Kadir Karabulut
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




@app.route("/orders", methods=["GET", "POST"])
def orders():
    if 'user_id' not in session:
        flash("Please log in to place an order.", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        user_id = session['user_id']
        payment_type = request.form.get('payment_type')
        card_name = request.form.get('card_name')
        card_number = request.form.get('card_number')
        card_expiration = request.form.get('card_expiration')
        bank_account_number = request.form.get('bank_account_number')
        bank_routing_number = request.form.get('bank_routing_number')

        
        if not payment_type or payment_type not in ['credit', 'debit', 'bank']:
            flash("Please select a valid payment type.", "danger")
            return redirect(url_for("orders"))

        if payment_type in ['credit', 'debit']:
            if not card_name or not card_number or not card_expiration:
                flash("Please fill in all card details.", "danger")
                return redirect(url_for("orders"))
            card_number_last4 = card_number[-4:]
            payment = OrderPayment(
                user_id=user_id,
                payment_type=payment_type,
                card_name=card_name,
                card_number_last4=card_number_last4,
                card_expiration=card_expiration
            )
        elif payment_type == 'bank':
            if not bank_account_number or not bank_routing_number:
                flash("Please fill in all bank account details.", "danger")
                return redirect(url_for("orders"))
            payment = OrderPayment(
                user_id=user_id,
                payment_type=payment_type,
                bank_account_number=bank_account_number,
                bank_routing_number=bank_routing_number
            )
        else:
            flash("Invalid payment type.", "danger")
            return redirect(url_for("orders"))

        try:
            db.session.add(payment)
            db.session.commit()
            flash("Order payment information saved! (Order logic can be extended here)", "success")
            return redirect(url_for("orders"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error saving payment: {str(e)}", "danger")
            return redirect(url_for("orders"))

    
    
    orders = []  
    return render_template("order.html", orders=orders)

# Portfolio management routes - by Kadir Karabulut
@app.route("/portfolio", methods=["GET", "POST"])
def portfolio():
    if 'user_id' not in session:
        flash("Please log in to view your portfolio.", "warning")
        return redirect(url_for("login"))

    user_id = session['user_id']

    if request.method == "POST":
        action = request.form.get("action", "add")

        if action == "delete":
            holding_id = request.form.get("holding_id")
            try:
                holding_id = int(holding_id)
            except (TypeError, ValueError):
                flash("Invalid request for deletion.", "danger")
                return redirect(url_for("portfolio"))

            holding = PortfolioHolding.query.filter_by(id=holding_id, user_id=user_id).first()
            if not holding:
                flash("Holding not found.", "warning")
                return redirect(url_for("portfolio"))

            db.session.delete(holding)
            db.session.commit()
            flash(f"Removed {holding.symbol} from your portfolio.", "info")
            return redirect(url_for("portfolio"))

        symbol = (request.form.get("symbol") or "").upper().strip()
        shares = request.form.get("shares")
        average_price = request.form.get("average_price")

        if not symbol or not shares or not average_price:
            flash("All fields are required to add a holding.", "danger")
        else:
            try:
                shares_value = float(shares)
                price_value = float(average_price)

                if shares_value <= 0 or price_value <= 0:
                    raise ValueError

                holding = PortfolioHolding.query.filter_by(user_id=user_id, symbol=symbol).first()

                if holding:
                    total_shares = holding.shares + shares_value
                    # Weighted average price for additional shares
                    holding.average_price = (
                        (holding.shares * holding.average_price) + (shares_value * price_value)
                    ) / total_shares
                    holding.shares = total_shares
                    holding.updated_at = datetime.utcnow()
                    flash(f"Updated holding for {symbol}.", "info")
                else:
                    holding = PortfolioHolding(
                        user_id=user_id,
                        symbol=symbol,
                        shares=shares_value,
                        average_price=price_value,
                    )
                    db.session.add(holding)
                    flash(f"Added {symbol} to your portfolio.", "success")

                db.session.commit()
            except ValueError:
                db.session.rollback()
                flash("Shares and price must be positive numbers.", "danger")
            except Exception as e:
                db.session.rollback()
                flash(f"Unable to save holding: {str(e)}", "danger")

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


@app.route('/customers', methods=['GET'])
def customers():
    if 'user_id' not in session:
        flash('Please log in to view your profile.', 'warning')
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    payment = OrderPayment.query.filter_by(user_id=user.id).first()
    return render_template('customers.html', user=user, payment=payment)


@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        flash('Please log in.', 'warning')
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    user.full_name = request.form.get('full_name')
    user.email = request.form.get('email')
    password = request.form.get('password')
    if password:
        user.password_hash = generate_password_hash(password)
    db.session.commit()
    flash('Profile updated!', 'success')
    return redirect(url_for('customers'))


@app.route('/save_payment_info', methods=['POST'])
def save_payment_info():
    if 'user_id' not in session:
        flash('Please log in.', 'warning')
        return redirect(url_for('login'))
    
    #Alert/leave as debugging for now testing in progress
    debug_info = f"Form data received: {request.form.to_dict()}\nUser ID: {session.get('user_id')}"
    flash(debug_info, 'info')
    
    try:
        user_id = session['user_id']
        payment_type = request.form.get('payment_type')
        card_name = request.form.get('card_name')
        card_number = request.form.get('card_number')
        card_expiration = request.form.get('card_expiration')
        bank_account_number = request.form.get('bank_account_number')
        bank_routing_number = request.form.get('bank_routing_number')
        
        #Alert/leave as debugging for now testing in progress
        flash(f"Processing payment info - Type: {payment_type}", 'info')

        payment = OrderPayment.query.filter_by(user_id=user_id).first()
        if not payment:
            payment = OrderPayment(user_id=user_id)
            db.session.add(payment)
            flash("Creating new payment record", 'info')
        else:
            flash("Updating existing payment record", 'info')

        payment.payment_type = payment_type
        if payment_type in ['credit', 'debit']:
            payment.card_name = card_name
            payment.card_number_last4 = card_number[-4:] if card_number else None
            flash(f"Processing card details - Name: {card_name}, Last4: {card_number[-4:] if card_number else 'None'}", 'info')
            
            if card_expiration:
                month, year = card_expiration.split('/')
                year = int(year)
                month = int(month)
                flash(f"Processing expiration date - Month: {month}, Year: {year}", 'info')
                
                #Validate expiration date
                current_year = datetime.now().year
                if year < current_year or year > current_year + 20:
                    raise ValueError("Card expiration year must be between current year and 20 years in the future")
                if month < 1 or month > 12:
                    raise ValueError("Invalid month in expiration date")
                    
                #MM/YYYY format
                payment.card_expiration = f"{month:02d}/{year}"
            payment.bank_account_number = None
            payment.bank_routing_number = None
        elif payment_type == 'bank':
            payment.card_name = None
            payment.card_number_last4 = None
            payment.card_expiration = None
            
            if bank_account_number:
                payment.bank_account_number = int(bank_account_number.replace('-', '').replace(' ', ''))
            if bank_routing_number:
                payment.bank_routing_number = int(bank_routing_number.replace('-', '').replace(' ', ''))

        db.session.commit()
        flash('Payment info saved!', 'success')
    except ValueError as e:
        db.session.rollback()
        flash('Invalid input format. Please check your entries.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error saving payment information: {str(e)}', 'danger')
    
    return redirect(url_for('customers'))



with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
