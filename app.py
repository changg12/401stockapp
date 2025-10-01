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


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
