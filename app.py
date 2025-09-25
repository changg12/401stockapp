from flask import Flask, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session
from datetime import datetime

app = Flask(__name__)
bootstrap = Bootstrap5(app)


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


@app.route("/")
def home():
    return render_template("stock.html")


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