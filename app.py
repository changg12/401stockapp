from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, time
import pytz

app = Flask(__name__)
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

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/portfolio')
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
