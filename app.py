import random
import re
import smtplib
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, session, flash, url_for
from flask_mysqldb import MySQL
from flask_session import Session
import MySQLdb.cursors  # Make sure this is imported



# Flask App Initialization
app = Flask(__name__)
app.secret_key = "your-secure-secret-key"

# Configure Flask Session
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# MySQL Configuration
app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = "Z@id2000"
app.config["MYSQL_DB"] = "user_auth"
mysql = MySQL(app)

# Email Configuration
EMAIL_ADDRESS = "firozakht143@gmail.com"
EMAIL_PASSWORD = "okiz qdwa qzar mzci"

@app.route("/")
def index():
    search_query = request.args.get("search", "").strip().lower()
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch all agencies
    cursor.execute("SELECT * FROM agencies")
    agencies = cursor.fetchall()

    # Apply filtering if there's a search query
    if search_query:
        agencies = [
            agency for agency in agencies
            if search_query in agency["agencies_name"].lower() 
            or search_query in agency["city"].lower() 
            or search_query in agency["country"].lower()
        ]

    # Fetch packages for each agency
    for agency in agencies:
        cursor.execute("""
            SELECT * FROM packages WHERE registration_id = %s
        """, (agency["registration_id"],))
        packages = cursor.fetchall()
        agency["packages"] = packages

    cursor.close()
    return render_template("index.html", agencies=agencies)


@app.route("/enter_email")
def enter_email():
    return render_template("email.html")

def is_valid_email(email):
    regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(regex, email)

def send_otp(email):
    """Generate and send OTP to the provided email."""
    if not is_valid_email(email):
        return False
    
    otp = str(random.randint(100000, 999999))
    session["otp"] = otp
    session["otp_expiry"] = (datetime.now() + timedelta(minutes=5)).timestamp()
    session["email"] = email
    session.modified = True
    
    subject = "Your OTP for Umrah Tour Login"
    message = f"Subject: {subject}\n\nYour OTP is: {otp} (Valid for 5 minutes)"
    
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, email, message)
        return True
    except smtplib.SMTPException:
        return False
    







@app.route("/send_otp", methods=["POST"])
def send_otp_route():
    email = request.form.get("email")
    
    if not email or not is_valid_email(email):
        flash("Invalid email!", "error")
        return redirect(url_for("enter_email"))
    
    if send_otp(email):
        return render_template("otp.html")
    else:
        flash("Failed to send OTP. Try again!", "error")
        return redirect(url_for("enter_email"))

@app.route("/verify_otp", methods=["POST"])
def verify_otp():
    entered_otp = request.form.get("otp")
    stored_otp = session.get("otp")
    otp_expiry = session.get("otp_expiry")
    email = session.get("email")

    if not stored_otp or not otp_expiry or datetime.now().timestamp() > otp_expiry:
        flash("OTP expired! Please request a new one.", "error")
        return redirect(url_for("enter_email"))

    if entered_otp.strip() == stored_otp.strip():
        try:
            cursor = mysql.connection.cursor()

            # Insert email if not exists
            cursor.execute("INSERT INTO users (email) VALUES (%s) ON DUPLICATE KEY UPDATE email=email", (email,))
            mysql.connection.commit()

            # Check if user details exist
            cursor.execute("SELECT first_name, last_name, personal_email FROM users WHERE email = %s", (email,))
            user_details = cursor.fetchone()
            cursor.close()

            session["logged_in"] = True
            session.modified = True

            if user_details and all(user_details):
                return redirect(url_for("business_dashboard"))
            else:
                return redirect(url_for("user_details"))

        except Exception as e:
            flash(f"Database error: {str(e)}", "error")
            return redirect(url_for("enter_email"))
    
    else:
        flash("Invalid OTP! Try again.", "error")
        return render_template("otp.html")

@app.route("/user_details", methods=["GET", "POST"])
def user_details():
    if not session.get("logged_in"):
        flash("Session expired. Please log in again.", "error")
        return redirect(url_for("enter_email"))

    if request.method == "POST":
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        personal_email = request.form.get("personal_email")
        email = session.get("email")

        if not first_name or not last_name or not personal_email:
            flash("All fields are required!", "error")
            return render_template("details.html")

        try:
            cursor = mysql.connection.cursor()
            cursor.execute(
                "UPDATE users SET first_name=%s, last_name=%s, personal_email=%s WHERE email=%s",
                (first_name, last_name, personal_email, email),
            )
            mysql.connection.commit()
            cursor.close()

            return redirect(url_for("business_dashboard"))

        except Exception as e:
            flash(f"Database error: {str(e)}", "error")
            return render_template("details.html")

    return render_template("details.html")



# @app.route('/business_dashboard')
# def business_dashboard():
#     if not session.get("logged_in"):
#         return redirect(url_for("enter_email"))

#     email = session.get("email")
#     cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

#     # Get agency details of the logged-in user
#     cursor.execute("SELECT * FROM agencies WHERE user_email = %s", (email,))
#     agencies = cursor.fetchall()

#     for agency in agencies:
#         # Get packages for each agency using correct column names
#         cursor.execute("""
#             SELECT package_id, package_name, days, price, description 
#             FROM packages 
#             WHERE agency_id = %s
#         """, (agency['id'],))  # agency['id'] is correct because 'id' is present in 'agencies' table
#         packages = cursor.fetchall()
#         agency['packages'] = packages

#     cursor.close()
#     return render_template("business_dashboard.html", agencies=agencies)

@app.route('/business_dashboard')
def business_dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("enter_email"))

    email = session.get("email")
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Step 1: Get user_id from email
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    if not user:
        flash("User not found!", "error")
        return redirect(url_for("enter_email"))

    user_id = user["id"]

    # Step 2: Get all agencies for the user
    cursor.execute("SELECT * FROM agencies WHERE user_id = %s", (user_id,))
    agencies = cursor.fetchall()

    # Step 3: Get packages for each agency
    for agency in agencies:
        cursor.execute("""
            SELECT package_id, package_name, days, price, description 
            FROM packages 
            WHERE registration_id = %s
        """, (agency['registration_id'],))  # use correct PK name
        packages = cursor.fetchall()
        agency['packages'] = packages

    cursor.close()
    return render_template("business_dashboard.html", agencies=agencies)


@app.route("/delete_agency/<int:agency_id>")
def delete_agency(registration_id):
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("DELETE FROM packages WHERE registration_id = %s", (registration_id,))
        cursor.execute("DELETE FROM agencies WHERE id = %s", (registration_id,))
        mysql.connection.commit()
        flash("Agency deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting agency: {e}", "error")
    finally:
        cursor.close()
    return redirect(url_for("business_dashboard"))


@app.route("/delete_package/<int:package_id>")
def delete_package(package_id):
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("DELETE FROM packages WHERE package_id = %s", (package_id,))
        mysql.connection.commit()
        flash("Package deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting package: {e}", "error")
    finally:
        cursor.close()
    return redirect(url_for("business_dashboard"))




@app.route("/logout")
def logout():
    session.clear()  # clears all session data
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))  # or your home/login page



@app.route("/add_agency", methods=["GET"])
def add_agency_page():
    if not session.get("logged_in"):
        flash("Session expired. Please log in again.", "error")
        return redirect(url_for("enter_email"))
    return render_template("add_agency.html")


@app.route("/save_agency", methods=["POST"])
def save_agency():
    if not session.get("logged_in"):
        flash("Session expired. Please log in again.", "error")
        return redirect(url_for("enter_email"))

    email = session.get("email")
    agencies_name = request.form.get("agency_name")  # matches `agencies_name` in DB
    country = request.form.get("country")
    city = request.form.get("city")
    description = request.form.get("description")

    if not agencies_name or not country or not city:
        flash("All fields are required!", "error")
        return redirect(url_for("add_agency_page"))

    try:
        cursor = mysql.connection.cursor()

        # Fetch the user's ID based on email
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if not user:
            flash("User not found in the database.", "error")
            return redirect(url_for("enter_email"))

        user_id = user[0]

        # Insert into agencies table
        sql = """
        INSERT INTO agencies (agencies_name, user_id, country, city, description) 
        VALUES (%s, %s, %s, %s, %s)
        """
        values = (agencies_name, user_id, country, city, description)
        cursor.execute(sql, values)
        mysql.connection.commit()
        cursor.close()

        flash("Agency added successfully!", "success")
    except Exception as e:
        flash(f"Database error: {str(e)}", "error")

    return redirect(url_for("business_dashboard"))


@app.route('/add_packages_page')
def add_packages_page():
    if not session.get("logged_in"):
        return redirect(url_for("enter_email"))

    email = session.get("email")
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Step 1: Get user ID
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    if not user:
        flash("User not found!", "error")
        return redirect(url_for("enter_email"))

    user_id = user["id"]

    # Step 2: Get agencies for this user
    cursor.execute("SELECT registration_id, agencies_name FROM agencies WHERE user_id = %s", (user_id,))
    agencies = cursor.fetchall()
    cursor.close()

    return render_template("add_packages.html", agencies=agencies)



@app.route("/save_package", methods=["POST"])
def save_package():
    if not session.get("logged_in"):
        flash("Session expired. Please log in again.", "error")
        return redirect(url_for("enter_email"))

    package_name = request.form.get("package_name")
    days = request.form.get("days")
    price = request.form.get("price")
    description = request.form.get("description")
    registration_id = request.form.get("registration_id")
    email = session.get("email")

    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO packages (registration_id, package_name, days, price, description)
            VALUES ( %s, %s, %s, %s, %s)
        """, (registration_id , package_name, days, price, description))
        mysql.connection.commit()
        cursor.close()
        flash("Package added successfully!", "success")
    except Exception as e:
        flash(f"Database Error: {e}", "error")

    return redirect(url_for("business_dashboard"))






if __name__ == "__main__":
    app.run(debug=True)
