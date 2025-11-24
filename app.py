from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session
from datetime import datetime, date, time, timedelta
from math import ceil
from sqlalchemy import func
import os
import random
import threading
import time as time_module
import pytz

app = Flask(__name__)
bootstrap = Bootstrap(app)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://admin:password@flaskdb.cxewmo2iqc1i.us-east-1.rds.amazonaws.com/flask_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'awdasdawdasdawdasdawdasd'

db = SQLAlchemy(app)


MARKET_TZ = pytz.timezone("America/New_York")
DEFAULT_MARKET_OPEN_TIME = time(9, 30)
DEFAULT_MARKET_CLOSE_TIME = time(16, 0)

RANDOM_PRICE_MAX_CHANGE = 50.0  # percent bounds for daily move
RANDOM_PRICE_STDDEV = 10.0  # bell curve spread (standard deviation)
RANDOM_PRICE_QUANTUM = 0.01  # enforce 0.01% increments
RANDOM_PRICE_CHECK_INTERVAL = 80  # run every 180 seconds

_random_price_thread = None
_random_price_lock = threading.Lock()
#_random_price_last_run_date = None


def shift_month_start(reference: datetime, months: int) -> datetime:
    """Return the first day of the month offset by `months` from `reference`."""
    month_index = (reference.month - 1) + months
    year = reference.year + month_index // 12
    month = (month_index % 12) + 1
    return datetime(year, month, 1)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
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
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    wallet_balance = db.Column(db.Float, default=0.0, nullable=False)



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


class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    shares = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    total_value = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(10), nullable=False)  # BUY or SELL
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class UserLoginLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    login_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    logout_at = db.Column(db.DateTime)


class MarketScheduleOverride(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    is_closed = db.Column(db.Boolean, default=False, nullable=False)
    open_time = db.Column(db.Time)
    close_time = db.Column(db.Time)
    note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    return User.query.get(user_id)


def require_admin_access():
    user = get_current_user()
    if not user:
        flash("Please log in to access the admin portal.", "warning")
        return False, redirect(url_for("login"))

    if not user.is_admin:
        flash("Administrator rights are required to view this page.", "danger")
        return False, redirect(url_for("home"))

    return True, user


def get_market_schedule_for_day(target_date):
    override = MarketScheduleOverride.query.filter_by(date=target_date).first()

    schedule = {
        "date": target_date,
        "is_closed": False,
        "open_time": DEFAULT_MARKET_OPEN_TIME,
        "close_time": DEFAULT_MARKET_CLOSE_TIME,
        "note": None,
        "override": override,
    }

    # Weekend default closure unless an override opens the market explicitly
    if target_date.weekday() >= 5:
        schedule["is_closed"] = True
        schedule["note"] = "Weekend closure"

    if override:
        schedule["is_closed"] = bool(override.is_closed)
        if override.note:
            schedule["note"] = override.note

        if not override.is_closed:
            if override.open_time:
                schedule["open_time"] = override.open_time
            if override.close_time:
                schedule["close_time"] = override.close_time
            if not override.note:
                schedule["note"] = None
        else:
            schedule["open_time"] = override.open_time
            schedule["close_time"] = override.close_time

    return schedule


def find_next_opening(start_date, reference_dt=None):
    # Search upcoming days for an open market session
    reference_dt = reference_dt or datetime.now(MARKET_TZ)
    for offset in range(0, 14):
        day = start_date + timedelta(days=offset)
        schedule = get_market_schedule_for_day(day)
        if schedule["is_closed"]:
            continue

        open_time = schedule.get("open_time") or DEFAULT_MARKET_OPEN_TIME
        open_dt = MARKET_TZ.localize(datetime.combine(day, open_time))
        if open_dt >= reference_dt:
            return open_dt

    return None


def get_market_status(reference=None):
    now = reference or datetime.now(MARKET_TZ)
    today = now.date()

    schedule = get_market_schedule_for_day(today)

    status = {
        "is_open": False,
        "message": None,
        "opens_at": None,
        "closes_at": None,
        "next_open": None,
        "note": schedule.get("note"),
    }

    if schedule["is_closed"] or not schedule.get("open_time") or not schedule.get("close_time"):
        note = schedule.get("note")
        if note:
            status["message"] = f"{note}. Trading is currently disabled."
        else:
            status["message"] = "Markets are closed today. Trading is currently disabled."
        status["next_open"] = find_next_opening(today + timedelta(days=1), reference_dt=now)
        return status

    open_time = schedule["open_time"] or DEFAULT_MARKET_OPEN_TIME
    close_time = schedule["close_time"] or DEFAULT_MARKET_CLOSE_TIME

    open_dt = MARKET_TZ.localize(datetime.combine(today, open_time))
    close_dt = MARKET_TZ.localize(datetime.combine(today, close_time))

    status["opens_at"] = open_dt
    status["closes_at"] = close_dt

    if open_dt <= now <= close_dt:
        status["is_open"] = True
        status["message"] = None
        status["next_open"] = open_dt
        return status

    if now < open_dt:
        status["message"] = "Markets are not open yet. Trading remains disabled until the session begins."
        status["next_open"] = open_dt
    else:
        status["message"] = "Markets are closed for the day. Trading will resume next session."
        status["next_open"] = find_next_opening(today + timedelta(days=1), reference_dt=now)

    return status


def format_market_notice(status):
    message = status.get("message") or "Markets are currently closed. Trading is disabled."
    next_open = status.get("next_open")
    if next_open:
        next_label = next_open.strftime('%A, %B %d at %I:%M %p %Z').lstrip('0')
        message = f"{message} Next session begins {next_label}."
    return message


def build_customer_activity_summary():
    users = User.query.order_by(User.full_name.asc()).all()
    if not users:
        return []

    now = datetime.utcnow()
    year_start = datetime(now.year, 1, 1)
    month_start = datetime(now.year, now.month, 1)

    from calendar import monthrange

    days_in_month = monthrange(now.year, now.month)[1]

    # Pre-seed metrics for each user to ensure deterministic ordering
    metrics = {
        user.id: {
            "display_name": user.full_name or user.email,
            "year_buy_total": 0.0,
            "year_sell_total": 0.0,
            "month_buy_total": 0.0,
            "month_sell_total": 0.0,
            "month_buy_daily_avg": 0.0,
            "month_sell_daily_avg": 0.0,
            "month_profit_loss": 0.0,
        }
        for user in users
    }

    # Fetch all trades from the start of the year to avoid multiple queries
    yearly_trades = Trade.query.filter(Trade.created_at >= year_start).all()

    for trade in yearly_trades:
        user_metrics = metrics.get(trade.user_id)
        if not user_metrics:
            continue

        is_buy = (trade.transaction_type or "").upper() == "BUY"

        if is_buy:
            user_metrics["year_buy_total"] += float(trade.total_value or 0)
        else:
            user_metrics["year_sell_total"] += float(trade.total_value or 0)

        if trade.created_at >= month_start:
            if is_buy:
                user_metrics["month_buy_total"] += float(trade.total_value or 0)
            else:
                user_metrics["month_sell_total"] += float(trade.total_value or 0)

    for data in metrics.values():
        if days_in_month:
            data["month_buy_daily_avg"] = data["month_buy_total"] / days_in_month
            data["month_sell_daily_avg"] = data["month_sell_total"] / days_in_month
        data["month_profit_loss"] = data["month_sell_total"] - data["month_buy_total"]

    return list(metrics.values())

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
    createdate = db.Column('createdate', db.DateTime, nullable=True, default=datetime.utcnow)

# Random Stock Price Generator based on Bell Curve (Gaussian distribution) centered zero (0.0) on the market open days.
def _generate_random_percent_change():
    change = random.gauss(0.0, RANDOM_PRICE_STDDEV)
    change = max(min(change, RANDOM_PRICE_MAX_CHANGE), -RANDOM_PRICE_MAX_CHANGE)
    quantized = round(change / RANDOM_PRICE_QUANTUM) * RANDOM_PRICE_QUANTUM
    if quantized > RANDOM_PRICE_MAX_CHANGE:
        return RANDOM_PRICE_MAX_CHANGE
    if quantized < -RANDOM_PRICE_MAX_CHANGE:
        return -RANDOM_PRICE_MAX_CHANGE
    return quantized


def _apply_random_price_adjustments():
    stocks = StockSymbol.query.all()
    updated = 0

    for stock in stocks:
        previous_price = stock.lastsale
        if previous_price is None or previous_price <= 0:
            stock.netchange = 0.0
            stock.pctchange = 0.0
            continue

        percent_change = _generate_random_percent_change()
        adjustment_factor = 1 + (percent_change / 100.0) 
        new_price = max(previous_price * adjustment_factor, 0.0)
        new_price = round(new_price, 2) 

        stock.lastsale = new_price
        stock.netchange = round(new_price - previous_price, 4) #netchange: round to 4 decimal like $11.4539
        stock.pctchange = round(percent_change, 2) #percent change: round to 2 decimal like 11.35, the increment is 0.01%
        updated += 1

    if not updated:
        return

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    app.logger.info("Random stock price generator updated %s symbols", updated)


def _random_price_generator_loop():
    with app.app_context():
        while True:
            market_status = get_market_status()
            if market_status.get("is_open"):
                try:
                    _apply_random_price_adjustments()
                except Exception: 
                    app.logger.exception("Random stock price generator failed")            
            time_module.sleep(RANDOM_PRICE_CHECK_INTERVAL)

def start_random_price_generator():
    global _random_price_thread
    with _random_price_lock:
        if _random_price_thread and _random_price_thread.is_alive():
            return

        _random_price_thread = threading.Thread(
            target=_random_price_generator_loop,
            name="RandomPriceGenerator",
            daemon=True,
        )
        _random_price_thread.start()

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



@app.route("/reports")
def reports():
    if 'user_id' not in session:
        flash("Please log in to view reports.", "warning")
        return redirect(url_for("login"))

    user_id = session['user_id']

    holdings = (
        PortfolioHolding.query
        .filter_by(user_id=user_id)
        .order_by(PortfolioHolding.symbol)
        .all()
    )

    total_cost_basis = sum((holding.shares or 0) * (holding.average_price or 0) for holding in holdings)

    symbol_set = {holding.symbol.upper() for holding in holdings}

    trades = (
        Trade.query
        .filter_by(user_id=user_id)
        .order_by(Trade.created_at.asc())
        .all()
    )

    symbol_set.update(trade.symbol.upper() for trade in trades)

    stock_rows = []
    if symbol_set:
        stock_rows = (
            StockSymbol.query
            .filter(StockSymbol.symbol.in_(symbol_set))
            .all()
        )

    stock_lookup = {row.symbol.upper(): row for row in stock_rows}
    price_lookup = {symbol: (row.lastsale or 0.0) for symbol, row in stock_lookup.items()}

    total_market_value = 0.0
    for holding in holdings:
        price = price_lookup.get(holding.symbol.upper())
        if price is None:
            continue
        total_market_value += (holding.shares or 0) * price

    total_buy_value = sum(float(trade.total_value or 0) for trade in trades if trade.transaction_type.upper() == "BUY")
    total_sell_value = sum(float(trade.total_value or 0) for trade in trades if trade.transaction_type.upper() == "SELL")

    realized_cost = total_buy_value - total_cost_basis
    if realized_cost < 0:
        realized_cost = 0.0

    total_performance = total_sell_value - realized_cost
    if realized_cost > 0:
        total_performance_pct = (total_performance / realized_cost) * 100.0
    elif total_performance == 0:
        total_performance_pct = 0.0
    else:
        total_performance_pct = None

    enriched_holdings = []
    for holding in holdings:
        symbol_key = holding.symbol.upper()
        stock = stock_lookup.get(symbol_key)
        current_price = stock.lastsale if stock and stock.lastsale is not None else None
        shares_value = float(holding.shares or 0)
        current_value = shares_value * current_price if current_price is not None else None
        average_price = holding.average_price if holding.average_price is not None else None
        cost_value = shares_value * average_price if average_price is not None else None

        enriched_holdings.append(
            {
                "holding": holding,
                "stock": stock,
                "current_price": current_price,
                "current_value": current_value,
                "cost_value": cost_value,
                "average_price": average_price,
                "pct_change": stock.pctchange if stock else None,
                "market": stock.market if stock else None,
            }
        )

    timeline = []

    def snapshot(timestamp: datetime, state: dict):
        total_cost = sum(item["cost"] for item in state.values())
        total_value = 0.0
        for symbol_key, data in state.items():
            price = price_lookup.get(symbol_key, 0.0)
            total_value += price * data["shares"]
        timeline.append({
            "timestamp": timestamp,
            "cost": total_cost,
            "value": total_value,
        })

    holdings_state = {}

    if trades:
        first_trade_time = trades[0].created_at - timedelta(seconds=1)
        snapshot(first_trade_time, holdings_state)

    for trade in trades:
        symbol_key = trade.symbol.upper()
        state = holdings_state.setdefault(symbol_key, {"shares": 0.0, "cost": 0.0})
        shares = float(trade.shares or 0)
        total_value = float(trade.total_value or 0)

        if trade.transaction_type.upper() == "BUY":
            state["shares"] += shares
            state["cost"] += total_value
        else:
            shares_to_sell = min(state["shares"], shares)
            if shares_to_sell > 0:
                avg_cost = state["cost"] / state["shares"] if state["shares"] else 0.0
                state["shares"] -= shares_to_sell
                state["cost"] -= avg_cost * shares_to_sell

        snapshot(trade.created_at, holdings_state)

    current_snapshot_time = datetime.utcnow()
    current_snapshot_state = {}
    for holding in holdings:
        current_snapshot_state[holding.symbol.upper()] = {
            "shares": float(holding.shares or 0),
            "cost": float((holding.shares or 0) * (holding.average_price or 0)),
        }

    snapshot(current_snapshot_time, current_snapshot_state)

    timeline.sort(key=lambda entry: entry["timestamp"])

    if not timeline:
        timeline.append({
            "timestamp": current_snapshot_time,
            "cost": total_cost_basis,
            "value": total_market_value,
        })

    chart_labels = [entry["timestamp"].strftime("%Y-%m-%d %H:%M") for entry in timeline]
    chart_cost_values = [round(entry["cost"], 2) for entry in timeline]
    chart_market_values = [round(entry["value"], 2) for entry in timeline]

    def latest_snapshot_before(target: datetime):
        selected = None
        for entry in timeline:
            if entry["timestamp"] <= target:
                selected = entry
            else:
                break
        return selected

    current_snapshot = timeline[-1]

    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    six_month_start = shift_month_start(month_start, -5)
    year_start = datetime(now.year, 1, 1)

    period_definitions = [
        ("month", "Calendar Month", month_start, 21),
        ("six_month", "Last 6 Months", six_month_start, 126),
        ("year", "Year to Date", year_start, 252),
    ]

    def compute_portfolio_growth(start_dt: datetime):
        baseline = latest_snapshot_before(start_dt)
        base_value = baseline["value"] if baseline else 0.0
        current_value = current_snapshot["value"]
        abs_change = current_value - base_value
        if base_value:
            pct_change = (abs_change / base_value) * 100.0
        else:
            pct_change = 0.0 if current_value == 0 else None
        return {
            "abs_change": abs_change,
            "pct_change": pct_change,
        }

    portfolio_performance = {
        key: compute_portfolio_growth(start_dt)
        for key, _, start_dt, _ in period_definitions
    }

    markets = ["NASDAQ", "NYSE", "AMEX"]
    market_rows = []
    for market in markets:
        sum_value, count_value = (
            db.session.query(
                func.coalesce(func.sum(StockSymbol.pctchange), 0),
                func.count(StockSymbol.symbol),
            )
            .filter(StockSymbol.market == market)
            .one()
        )

        avg_daily_change = (sum_value / count_value) if count_value else 0.0

        values = {}
        for key, _, _, trading_days in period_definitions:
            if avg_daily_change:
                compounded = (pow(1 + (avg_daily_change / 100.0), trading_days) - 1) * 100.0
            else:
                compounded = 0.0
            values[key] = compounded

        display_name = "APEX" if market == "AMEX" else market
        market_rows.append({
            "label": display_name,
            "values": values,
        })

    performance_rows = [
        {
            "label": "Portfolio",
            "values": {key: portfolio_performance[key]["pct_change"] for key, _, _, _ in period_definitions},
        }
    ] + market_rows

    return render_template(
        "reports.html",
        chart_labels=chart_labels,
        chart_cost_values=chart_cost_values,
        chart_market_values=chart_market_values,
        total_cost_basis=total_cost_basis,
        total_market_value=total_market_value,
        total_buy_value=total_buy_value,
        total_sell_value=total_sell_value,
        total_performance=total_performance,
        total_performance_pct=total_performance_pct,
        realized_cost=realized_cost,
        period_definitions=period_definitions,
        performance_rows=performance_rows,
        portfolio_performance=portfolio_performance,
        holding_rows=enriched_holdings,
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
            session['is_admin'] = bool(user.is_admin)

            login_log = UserLoginLog(user_id=user.id)
            db.session.add(login_log)
            db.session.commit()

            flash("Login successful!", "success")
            return render_template("login.html", redirect_to_home=True)
        else:
            flash("Invalid email or password", "danger")
            return render_template("login.html", redirect_to_home=False)


    return render_template("login.html")


@app.route("/logout")
def logout():
    user_id = session.get('user_id')
    if user_id:
        latest_log = (
            UserLoginLog.query
            .filter_by(user_id=user_id, logout_at=None)
            .order_by(UserLoginLog.login_at.desc())
            .first()
        )
        if latest_log:
            latest_log.logout_at = datetime.utcnow()
            db.session.commit()

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

    market_status = get_market_status()
    market_open = market_status.get("is_open")
    market_notice = format_market_notice(market_status) if not market_open else None

    if request.method == "POST":
        market_status = get_market_status()
        if not market_status.get("is_open"):
            flash(format_market_notice(market_status), "warning")
            return redirect(url_for("portfolio"))

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

            stock_row = (
                StockSymbol.query
                .filter(func.upper(StockSymbol.symbol) == holding.symbol.upper())
                .order_by(StockSymbol.market)
                .first()
            )

            price_value = None
            if stock_row and stock_row.lastsale is not None and stock_row.lastsale > 0:
                price_value = float(stock_row.lastsale)
            elif holding.average_price:
                price_value = float(holding.average_price)
            else:
                price_value = 0.0

            total_value = float(holding.shares or 0) * price_value

            symbol_str = holding.symbol.upper()

            trade_entry = Trade(
                user_id=user_id,
                symbol=symbol_str,
                shares=holding.shares,
                price=price_value,
                total_value=total_value,
                transaction_type="SELL",
            )

            db.session.add(trade_entry)

            db.session.delete(holding)
            user.wallet_balance += total_value
            db.session.commit()
            flash(f"Sold {symbol_str}. ${total_value:.2f} added to your wallet.", "info")
            return redirect(url_for("portfolio"))

        symbol = (request.form.get("symbol") or "").upper().strip()
        shares = request.form.get("shares")

        if not symbol or not shares:
            flash("Symbol and shares are required to add a stock holding.", "danger")
        else:
            try:
                shares_value = float(shares)
                if shares_value <= 0:
                    raise ValueError

                stock_row = (
                    StockSymbol.query
                    .filter(func.upper(StockSymbol.symbol) == symbol)
                    .order_by(StockSymbol.market)
                    .first()
                )

                if not stock_row or stock_row.lastsale is None:
                    flash("Unable to find a last sale price for that symbol.", "warning")
                    return redirect(url_for("portfolio"))

                price_value = float(stock_row.lastsale)

                if price_value <= 0:
                    flash("Last sale price must be a positive number.", "danger")
                    return redirect(url_for("portfolio"))

                total_cost = shares_value * price_value
                if user.wallet_balance < total_cost:
                    flash("Insufficient wallet balance. Deposit funds into your wallet before buying.", "warning")
                    return redirect(url_for("portfolio"))

                holding = PortfolioHolding.query.filter_by(user_id=user_id, symbol=symbol).first()

                if holding:
                    total_shares = holding.shares + shares_value
                    holding.average_price = (
                        (holding.shares * holding.average_price) + (shares_value * price_value)
                    ) / total_shares
                    holding.shares = total_shares
                    holding.updated_at = datetime.utcnow()
                    flash(f"Updated stock holding for {symbol}.", "info")
                else:
                    holding = PortfolioHolding(
                        user_id=user_id,
                        symbol=symbol,
                        shares=shares_value,
                        average_price=price_value,
                    )
                    db.session.add(holding)
                    flash(f"Added {symbol} to your portfolio using wallet funds.", "success")

                trade_entry = Trade(
                    user_id=user_id,
                    symbol=symbol,
                    shares=shares_value,
                    price=price_value,
                    total_value=total_cost,
                    transaction_type="BUY",
                )

                user.wallet_balance -= total_cost

                db.session.add(trade_entry)
                db.session.commit()
            except ValueError:
                db.session.rollback()
                flash("Shares must be a positive number.", "danger")
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
        average_price = holding.average_price if holding.average_price is not None else None
        cost_value = holding.shares * average_price if average_price is not None else None
        if current_value is not None:
            total_market_value += current_value
            has_market_value = True

        enriched_holdings.append(
            {
                "holding": holding,
                "stock": stock,
                "current_price": current_price,
                "current_value": current_value,
                "cost_value": cost_value,
                "average_price": average_price,
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

    ipo_stocks = (
        StockSymbol.query
        .filter(StockSymbol.createdate.isnot(None))
        .order_by(StockSymbol.createdate.desc(), StockSymbol.symbol)
        .limit(25)
        .all()
    )

    return render_template(
        "portfolio.html",
        holdings=enriched_holdings,
        total_cost_basis=total_cost_basis,
        total_market_value=total_market_value,
        unrealized_pl=unrealized_pl,
        market_open=market_open,
        market_notice=market_notice,
        market_status=market_status,
        wallet_balance=user.wallet_balance,
        ipo_stocks=ipo_stocks,
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
        full_name = (request.form.get("full_name") or "").strip()
        email = request.form.get("email")
        password = request.form.get("password")

        password_hash = generate_password_hash(password)

        first_name = None
        last_name = None
        if full_name:
            name_parts = full_name.split(None, 1)
            first_name = name_parts[0]
            if len(name_parts) > 1:
                last_name = name_parts[1]

        new_user = User(
            full_name=full_name or email,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password_hash=password_hash,
        )
        db.session.add(new_user)
        db.session.commit()

        flash("Account created successfully!", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


with app.app_context():
    db.create_all()
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_random_price_generator()

if __name__ == "__main__":
    app.run(debug=True)
