from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_mysqldb import MySQL
from flask_mail import Mail, Message
from datetime import datetime, timedelta
import pymysql
import os
import json
import hashlib
import uuid
from functools import wraps
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Initialize MySQL
mysql = MySQL(app)

# Initialize Mail
mail = Mail(app)

# Helper Functions
def get_db_connection():
    return mysql.connection

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_order_id():
    return str(uuid.uuid4())[:8].upper()

def safe_float(value):
    """Safely convert value to float, handling None"""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

def safe_int(value):
    """Safely convert value to int, handling None"""
    if value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0

def calculate_credit_score(user_id):
    """Calculate credit score based on user behavior"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_orders,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_orders,
                SUM(CASE WHEN payment_status = 'failed' THEN 1 ELSE 0 END) as failed_payments,
                AVG(restaurant_feedback) as avg_restaurant_feedback,
                AVG(delivery_feedback) as avg_delivery_feedback
            FROM orders 
            WHERE user_id = %s
        """, (user_id,))
        
        result = cursor.fetchone()
        
        if not result:
            return Config.DEFAULT_CREDIT_SCORE
        
        total_orders = safe_int(result[0])
        completed_orders = safe_int(result[1])
        cancelled_orders = safe_int(result[2])
        failed_payments = safe_int(result[3])
        avg_restaurant_feedback = safe_float(result[4])
        avg_delivery_feedback = safe_float(result[5])
        
        # Base score
        score = Config.DEFAULT_CREDIT_SCORE
        
        # Adjustments based on behavior
        if total_orders > 0:
            completion_rate = completed_orders / total_orders
            cancellation_rate = cancelled_orders / total_orders
            
            # Positive factors
            if completion_rate > 0.9:
                score += 10
            elif completion_rate > 0.7:
                score += 5
            
            # Negative factors
            if cancellation_rate > 0.3:
                score -= 20
            elif cancellation_rate > 0.1:
                score -= 10
            
            if failed_payments > 0:
                score -= (failed_payments * 5)
            
            # Feedback impact
            if avg_restaurant_feedback > 4.0:
                score += 5
            elif avg_restaurant_feedback < 2.0:
                score -= 10
            
            if avg_delivery_feedback > 4.0:
                score += 3
            elif avg_delivery_feedback < 2.0:
                score -= 5
        
        # Ensure score stays within bounds
        score = max(0, min(100, score))
        
        return int(score)
        
    except Exception as e:
        print(f"Error calculating credit score: {e}")
        return Config.DEFAULT_CREDIT_SCORE
    finally:
        cursor.close()

def update_user_credit_score(user_id):
    """Update user's credit score in database"""
    score = calculate_credit_score(user_id)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE users 
            SET credit_score = %s,
                credit_status = CASE 
                    WHEN %s >= 90 THEN 'trusted'
                    WHEN %s >= 75 THEN 'good'
                    WHEN %s >= 50 THEN 'average'
                    WHEN %s >= 30 THEN 'risky'
                    ELSE 'blocked'
                END,
                last_credit_update = %s
            WHERE id = %s
        """, (score, score, score, score, score, datetime.now(), user_id))
        conn.commit()
        return score
    except Exception as e:
        print(f"Error updating credit score: {e}")
        return None
    finally:
        cursor.close()

def login_required(role=None):
    """Decorator to require login and optionally specific role"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            
            if role and session.get('role') != role:
                flash('Unauthorized access', 'error')
                return redirect(url_for('dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def send_email(subject, recipient, body):
    """Send email using Flask-Mail"""
    try:
        msg = Message(
            subject=subject,
            recipients=[recipient],
            body=body,
            sender=app.config['MAIL_USERNAME']
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# Database Initialization
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create tables
    tables_sql = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            name VARCHAR(100) NOT NULL,
            phone VARCHAR(20),
            address TEXT,
            role ENUM('customer', 'restaurant', 'admin', 'delivery') DEFAULT 'customer',
            credit_score INT DEFAULT 70,
            credit_status ENUM('trusted', 'good', 'average', 'risky', 'blocked') DEFAULT 'average',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_credit_update TIMESTAMP NULL,
            is_active BOOLEAN DEFAULT TRUE,
            INDEX idx_email (email),
            INDEX idx_role (role)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS restaurants (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            address TEXT NOT NULL,
            phone VARCHAR(20),
            email VARCHAR(100),
            cuisine_type VARCHAR(50),
            opening_time TIME,
            closing_time TIME,
            is_open BOOLEAN DEFAULT TRUE,
            avg_prep_time INT DEFAULT 30,
            rating DECIMAL(3,2) DEFAULT 0.0,
            total_ratings INT DEFAULT 0,
            trust_badge BOOLEAN DEFAULT FALSE,
            latitude DECIMAL(10,8),
            longitude DECIMAL(11,8),
            commission_rate DECIMAL(5,2) DEFAULT 15.00,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_cuisine (cuisine_type),
            INDEX idx_open (is_open)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS menu_items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            restaurant_id INT NOT NULL,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            price DECIMAL(10,2) NOT NULL,
            category VARCHAR(50),
            is_available BOOLEAN DEFAULT TRUE,
            image_url VARCHAR(255),
            prep_time INT DEFAULT 15,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE,
            INDEX idx_restaurant (restaurant_id),
            INDEX idx_category (category)
        )
        """,
        """

CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_number VARCHAR(50) UNIQUE NOT NULL,
    user_id INT NOT NULL,
    restaurant_id INT NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    delivery_fee DECIMAL(10,2) DEFAULT 0.00,
    discount_amount DECIMAL(10,2) DEFAULT 0.00,
    final_amount DECIMAL(10,2) NOT NULL,
    delivery_address TEXT NOT NULL,
    payment_method ENUM('cod', 'card', 'wallet', 'netbanking') NOT NULL DEFAULT 'cod',
    payment_status ENUM('pending', 'completed', 'failed') DEFAULT 'pending',
    status ENUM('pending', 'accepted', 'preparing', 'ready', 'out_for_delivery', 'delivered', 'cancelled') DEFAULT 'pending',
    customer_credit_score INT,
    restaurant_feedback DECIMAL(2,1),
    delivery_feedback DECIMAL(2,1),
    cancelled_by ENUM('customer', 'restaurant', 'system', 'delivery') NULL,
    cancellation_reason TEXT,
    estimated_delivery_time TIMESTAMP NULL,
    actual_delivery_time TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE,
    INDEX idx_user (user_id),
    INDEX idx_restaurant (restaurant_id),
    INDEX idx_status (status),
    INDEX idx_created (created_at)
)
""",
        """
        CREATE TABLE IF NOT EXISTS order_items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL,
            menu_item_id INT NOT NULL,
            quantity INT NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            notes TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY (menu_item_id) REFERENCES menu_items(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS credit_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            old_score INT,
            new_score INT,
            change_amount INT,
            reason VARCHAR(255),
            triggered_by ENUM('system', 'admin', 'restaurant', 'delivery'),
            reference_id INT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_user (user_id),
            INDEX idx_created (created_at)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS customer_feedback (
            id INT AUTO_INCREMENT PRIMARY KEY,
            restaurant_id INT NOT NULL,
            user_id INT NOT NULL,
            order_id INT NOT NULL,
            politeness_rating INT CHECK (politeness_rating BETWEEN 1 AND 5),
            pickup_punctuality INT CHECK (pickup_punctuality BETWEEN 1 AND 5),
            order_authenticity INT CHECK (order_authenticity BETWEEN 1 AND 5),
            overall_rating DECIMAL(2,1),
            comments TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
            UNIQUE KEY unique_order_feedback (order_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS admin_actions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            admin_id INT NOT NULL,
            action_type VARCHAR(50) NOT NULL,
            target_type ENUM('user', 'restaurant', 'order', 'delivery') NOT NULL,
            target_id INT NOT NULL,
            details TEXT,
            ip_address VARCHAR(45),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (admin_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_admin (admin_id),
            INDEX idx_action (action_type)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            title VARCHAR(100) NOT NULL,
            message TEXT NOT NULL,
            type ENUM('info', 'warning', 'success', 'error') DEFAULT 'info',
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_user (user_id),
            INDEX idx_unread (is_read)
        )
        """
    ]
    
    for sql in tables_sql:
        try:
            cursor.execute(sql)
        except Exception as e:
            print(f"Error creating table: {e}")
    
    # Create default admin user if not exists
    cursor.execute("SELECT * FROM users WHERE email = 'admin@foodapp.com'")
    if not cursor.fetchone():
        admin_password = hash_password("admin123")
        cursor.execute("""
            INSERT INTO users (email, password, name, role, credit_score, credit_status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, ('admin@foodapp.com', admin_password, 'System Admin', 'admin', 100, 'trusted'))
    
    conn.commit()
    cursor.close()

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, password, name, role, credit_score, credit_status, is_active, email
            FROM users 
            WHERE email = %s
        """, (email,))
        
        user = cursor.fetchone()
        cursor.close()
        
        if user and user[1] == hash_password(password):
            if not user[6]:  # is_active at index 6
                flash('Your account has been deactivated. Please contact support.', 'error')
                return redirect(url_for('login'))
            
            session['user_id'] = user[0]      # id
            session['user_name'] = user[2]    # name
            session['role'] = user[3]         # role
            session['credit_score'] = user[4] # credit_score
            session['credit_status'] = user[5] # credit_status
            session['email'] = user[7]        # email
            
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role', 'customer')
        phone = request.form.get('phone', '')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))
        
        hashed_password = hash_password(password)
        
        cursor.execute("""
            INSERT INTO users (email, password, name, phone, role, credit_score, credit_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (email, hashed_password, name, phone, role, Config.DEFAULT_CREDIT_SCORE, 'average'))
        
        user_id = cursor.lastrowid
        
        # If registering as restaurant, create restaurant entry
        if role == 'restaurant':
            restaurant_name = request.form.get('restaurant_name', f"{name}'s Restaurant")
            address = request.form.get('address', '')
            cuisine = request.form.get('cuisine_type', 'Multi-cuisine')
            
            cursor.execute("""
                INSERT INTO restaurants (user_id, name, address, cuisine_type)
                VALUES (%s, %s, %s, %s)
            """, (user_id, restaurant_name, address, cuisine))
        
        conn.commit()
        cursor.close()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/register.html')

@app.route('/dashboard')
@login_required()
def dashboard():
    role = session.get('role')
    
    if role == 'customer':
        return redirect(url_for('customer_dashboard'))
    elif role == 'restaurant':
        return redirect(url_for('restaurant_dashboard'))
    elif role == 'admin':
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('index'))



# @app.route('/customer/dashboard')
# @login_required('customer')
# def customer_dashboard():
#     user_id = session['user_id']
    
#     conn = get_db_connection()
#     cursor = conn.cursor()
    
#     # Get user details
#     cursor.execute("""
#         SELECT u.*, COUNT(o.id) as total_orders,
#                SUM(CASE WHEN o.status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
#                SUM(CASE WHEN o.status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_orders
#         FROM users u
#         LEFT JOIN orders o ON u.id = o.user_id
#         WHERE u.id = %s
#         GROUP BY u.id
#     """, (user_id,))
    
#     user_tuple = cursor.fetchone()
    
#     # Convert tuple to dict
#     if user_tuple:
#         user = {
#             'id': user_tuple[0],
#             'email': user_tuple[1],
#             'name': user_tuple[3],
#             'phone': user_tuple[4],
#             'address': user_tuple[5],
#             'role': user_tuple[6],
#             'credit_score': user_tuple[7],
#             'credit_status': user_tuple[8],
#             'total_orders': safe_int(user_tuple[11]),
#             'completed_orders': safe_int(user_tuple[12]),
#             'cancelled_orders': safe_int(user_tuple[13])
#         }
#     else:
#         user = {}
    
#     # Get recent orders
#     cursor.execute("""
#         SELECT o.*, r.name as restaurant_name, r.trust_badge
#         FROM orders o
#         JOIN restaurants r ON o.restaurant_id = r.id
#         WHERE o.user_id = %s
#         ORDER BY o.created_at DESC
#         LIMIT 10
#     """, (user_id,))
    
#     recent_orders_tuples = cursor.fetchall()
#     recent_orders = []
#     for order in recent_orders_tuples:
#         recent_orders.append({
#             'id': order[0],
#             'order_number': order[1],
#             'user_id': order[2],
#             'restaurant_id': order[3],
#             'total_amount': safe_float(order[4]),
#             'delivery_fee': safe_float(order[5]),
#             'discount_amount': safe_float(order[6]),
#             'final_amount': safe_float(order[7]),
#             'delivery_address': order[8],
#             'payment_method': order[9],
#             'payment_status': order[10],
#             'status': order[11],
#             'customer_credit_score': order[12],
#             'created_at': order[20],
#             'restaurant_name': order[23],
#             'trust_badge': bool(order[24])
#         })
    
#     # Get notifications
#     cursor.execute("""
#         SELECT * FROM notifications 
#         WHERE user_id = %s AND is_read = FALSE
#         ORDER BY created_at DESC
#         LIMIT 10
#     """, (user_id,))
    
#     notifications_tuples = cursor.fetchall()
#     notifications = []
#     for note in notifications_tuples:
#         notifications.append({
#             'id': note[0],
#             'user_id': note[1],
#             'title': note[2],
#             'message': note[3],
#             'type': note[4],
#             'is_read': bool(note[5]),
#             'created_at': note[6]
#         })
    
#     cursor.close()
    
#     # Calculate discount based on credit score
#     credit_score = session.get('credit_score', 70)
#     discount_percentage = 0
    
#     if credit_score >= 90:
#         discount_percentage = 20
#     elif credit_score >= 75:
#         discount_percentage = 15
#     elif credit_score >= 50:
#         discount_percentage = 10
#     elif credit_score >= 30:
#         discount_percentage = 5
    
#     return render_template('customer/dashboard.html',
#                          user=user,
#                          orders=recent_orders,
#                          notifications=notifications,
#                          discount=discount_percentage,
#                          credit_score_ranges=Config.CREDIT_SCORE_RANGES)



@app.route('/customer/dashboard')
@login_required('customer')
def customer_dashboard():
    user_id = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user details
    cursor.execute("""
        SELECT u.*, COUNT(o.id) as total_orders,
               SUM(CASE WHEN o.status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
               SUM(CASE WHEN o.status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_orders
        FROM users u
        LEFT JOIN orders o ON u.id = o.user_id
        WHERE u.id = %s
        GROUP BY u.id
    """, (user_id,))
    
    user_tuple = cursor.fetchone()
    
    # Convert tuple to dict
    if user_tuple:
        user = {
            'id': user_tuple[0],
            'email': user_tuple[1],
            'name': user_tuple[3],
            'phone': user_tuple[4],
            'address': user_tuple[5],
            'role': user_tuple[6],
            'credit_score': user_tuple[7],
            'credit_status': user_tuple[8],
            'total_orders': safe_int(user_tuple[11]),
            'completed_orders': safe_int(user_tuple[12]),
            'cancelled_orders': safe_int(user_tuple[13])
        }
    else:
        user = {}
    
    # Get recent orders - FIXED: Simplified query to avoid index errors
    cursor.execute("""
        SELECT o.id, o.order_number, o.user_id, o.restaurant_id, o.total_amount,
               o.delivery_fee, o.discount_amount, o.final_amount, o.delivery_address,
               o.payment_method, o.payment_status, o.status, o.customer_credit_score,
               o.created_at, r.name as restaurant_name, r.trust_badge
        FROM orders o
        JOIN restaurants r ON o.restaurant_id = r.id
        WHERE o.user_id = %s
        ORDER BY o.created_at DESC
        LIMIT 10
    """, (user_id,))
    
    recent_orders_tuples = cursor.fetchall()
    recent_orders = []
    for order in recent_orders_tuples:
        recent_orders.append({
            'id': order[0],
            'order_number': order[1],
            'user_id': order[2],
            'restaurant_id': order[3],
            'total_amount': safe_float(order[4]),
            'delivery_fee': safe_float(order[5]),
            'discount_amount': safe_float(order[6]),
            'final_amount': safe_float(order[7]),
            'delivery_address': order[8],
            'payment_method': order[9],
            'payment_status': order[10],
            'status': order[11],
            'customer_credit_score': order[12],
            'created_at': order[13],
            'restaurant_name': order[14],
            'trust_badge': bool(order[15])
        })
    
    # Get notifications
    cursor.execute("""
        SELECT id, user_id, title, message, type, is_read, created_at
        FROM notifications 
        WHERE user_id = %s AND is_read = FALSE
        ORDER BY created_at DESC
        LIMIT 10
    """, (user_id,))
    
    notifications_tuples = cursor.fetchall()
    notifications = []
    for note in notifications_tuples:
        notifications.append({
            'id': note[0],
            'user_id': note[1],
            'title': note[2],
            'message': note[3],
            'type': note[4],
            'is_read': bool(note[5]),
            'created_at': note[6]
        })
    
    cursor.close()
    
    # Calculate discount based on credit score
    credit_score = session.get('credit_score', 70)
    discount_percentage = 0
    
    if credit_score >= 90:
        discount_percentage = 20
    elif credit_score >= 75:
        discount_percentage = 15
    elif credit_score >= 50:
        discount_percentage = 10
    elif credit_score >= 30:
        discount_percentage = 5
    
    return render_template('customer/dashboard.html',
                         user=user,
                         orders=recent_orders,
                         notifications=notifications,
                         discount=discount_percentage,
                         credit_score_ranges=Config.CREDIT_SCORE_RANGES)

# @app.route('/customer/orders')
# @login_required('customer')
# def customer_orders():
#     user_id = session['user_id']
    
#     conn = get_db_connection()
#     cursor = conn.cursor()
    
#     # Get user details
#     cursor.execute("""
#         SELECT u.*, COUNT(o.id) as total_orders,
#                SUM(CASE WHEN o.status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
#                SUM(CASE WHEN o.status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_orders
#         FROM users u
#         LEFT JOIN orders o ON u.id = o.user_id
#         WHERE u.id = %s
#         GROUP BY u.id
#     """, (user_id,))
    
#     user_tuple = cursor.fetchone()
    
#     if user_tuple:
#         user = {
#             'id': user_tuple[0],
#             'email': user_tuple[1],
#             'name': user_tuple[3],
#             'phone': user_tuple[4],
#             'address': user_tuple[5],
#             'role': user_tuple[6],
#             'credit_score': user_tuple[7],
#             'credit_status': user_tuple[8],
#             'total_orders': safe_int(user_tuple[11]),
#             'completed_orders': safe_int(user_tuple[12]),
#             'cancelled_orders': safe_int(user_tuple[13])
#         }
#     else:
#         user = {}
    
#     # Get all orders
#     cursor.execute("""
#         SELECT o.*, r.name as restaurant_name, r.trust_badge
#         FROM orders o
#         JOIN restaurants r ON o.restaurant_id = r.id
#         WHERE o.user_id = %s
#         ORDER BY o.created_at DESC
#     """, (user_id,))
    
#     orders_tuples = cursor.fetchall()
#     orders = []
#     for order in orders_tuples:
#         orders.append({
#             'id': order[0],
#             'order_number': order[1],
#             'user_id': order[2],
#             'restaurant_id': order[3],
#             'total_amount': safe_float(order[4]),
#             'delivery_fee': safe_float(order[5]),
#             'discount_amount': safe_float(order[6]),
#             'final_amount': safe_float(order[7]),
#             'delivery_address': order[8],
#             'payment_method': order[9],
#             'payment_status': order[10],
#             'status': order[11],
#             'customer_credit_score': order[12],
#             'created_at': order[20],
#             'restaurant_name': order[23],
#             'trust_badge': bool(order[24])
#         })
    
#     # Calculate discount
#     credit_score = session.get('credit_score', 70)
#     discount_percentage = 0
    
#     if credit_score >= 90:
#         discount_percentage = 20
#     elif credit_score >= 75:
#         discount_percentage = 15
#     elif credit_score >= 50:
#         discount_percentage = 10
#     elif credit_score >= 30:
#         discount_percentage = 5
    
#     cursor.close()
    
#     return render_template('customer/orders.html',
#                          user=user,
#                          orders=orders,
#                          discount=discount_percentage)



# @app.route('/customer/orders')
# @login_required('customer')
# def customer_orders():
#     user_id = session['user_id']
    
#     conn = get_db_connection()
#     cursor = conn.cursor()
    
#     # Get user details
#     cursor.execute("""
#         SELECT u.*, COUNT(o.id) as total_orders,
#                SUM(CASE WHEN o.status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
#                SUM(CASE WHEN o.status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_orders
#         FROM users u
#         LEFT JOIN orders o ON u.id = o.user_id
#         WHERE u.id = %s
#         GROUP BY u.id
#     """, (user_id,))
    
#     user_tuple = cursor.fetchone()
    
#     if user_tuple:
#         user = {
#             'id': user_tuple[0],
#             'email': user_tuple[1],
#             'name': user_tuple[3],
#             'phone': user_tuple[4],
#             'address': user_tuple[5],
#             'role': user_tuple[6],
#             'credit_score': user_tuple[7],
#             'credit_status': user_tuple[8],
#             'total_orders': safe_int(user_tuple[11]),
#             'completed_orders': safe_int(user_tuple[12]),
#             'cancelled_orders': safe_int(user_tuple[13])
#         }
#     else:
#         user = {}
    
#     # Get all orders with restaurant details
#     cursor.execute("""
#         SELECT o.*, r.name as restaurant_name, r.trust_badge,
#                COUNT(oi.id) as item_count,
#                GROUP_CONCAT(mi.name SEPARATOR ', ') as item_names
#         FROM orders o
#         JOIN restaurants r ON o.restaurant_id = r.id
#         LEFT JOIN order_items oi ON o.id = oi.order_id
#         LEFT JOIN menu_items mi ON oi.menu_item_id = mi.id
#         WHERE o.user_id = %s
#         GROUP BY o.id
#         ORDER BY o.created_at DESC
#     """, (user_id,))
    
#     orders_tuples = cursor.fetchall()
#     orders = []
#     for order in orders_tuples:
#         orders.append({
#             'id': order[0],
#             'order_number': order[1],
#             'user_id': order[2],
#             'restaurant_id': order[3],
#             'total_amount': safe_float(order[4]),
#             'delivery_fee': safe_float(order[5]),
#             'discount_amount': safe_float(order[6]),
#             'final_amount': safe_float(order[7]),
#             'delivery_address': order[8],
#             'payment_method': order[9],
#             'payment_status': order[10],
#             'status': order[11],
#             'customer_credit_score': safe_int(order[12]),
#             'created_at': order[20],
#             'updated_at': order[21],
#             'restaurant_name': order[22],
#             'trust_badge': bool(order[23]),
#             'item_count': safe_int(order[24]),
#             'item_names': order[25] if order[25] else 'No items'
#         })
    
#     # Calculate discount
#     credit_score = session.get('credit_score', 70)
#     discount_percentage = 0
    
#     if credit_score >= 90:
#         discount_percentage = 20
#     elif credit_score >= 75:
#         discount_percentage = 15
#     elif credit_score >= 50:
#         discount_percentage = 10
#     elif credit_score >= 30:
#         discount_percentage = 5
    
#     cursor.close()
    
#     return render_template('customer/orders.html',
#                          user=user,
#                          orders=orders,
#                          discount=discount_percentage)



@app.route('/customer/orders')
@login_required('customer')
def customer_orders():
    user_id = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user details
    cursor.execute("""
        SELECT u.*, COUNT(o.id) as total_orders,
               SUM(CASE WHEN o.status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
               SUM(CASE WHEN o.status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_orders
        FROM users u
        LEFT JOIN orders o ON u.id = o.user_id
        WHERE u.id = %s
        GROUP BY u.id
    """, (user_id,))
    
    user_tuple = cursor.fetchone()
    
    if user_tuple:
        user = {
            'id': user_tuple[0],
            'email': user_tuple[1],
            'name': user_tuple[3],
            'phone': user_tuple[4],
            'address': user_tuple[5],
            'role': user_tuple[6],
            'credit_score': user_tuple[7],
            'credit_status': user_tuple[8],
            'total_orders': safe_int(user_tuple[11]),
            'completed_orders': safe_int(user_tuple[12]),
            'cancelled_orders': safe_int(user_tuple[13])
        }
    else:
        user = {}
    
    # Get all orders - FIXED: Simplified query
    cursor.execute("""
        SELECT o.id, o.order_number, o.user_id, o.restaurant_id, o.total_amount,
               o.delivery_fee, o.discount_amount, o.final_amount, o.delivery_address,
               o.payment_method, o.payment_status, o.status, o.customer_credit_score,
               o.created_at, o.updated_at, r.name as restaurant_name, r.trust_badge
        FROM orders o
        JOIN restaurants r ON o.restaurant_id = r.id
        WHERE o.user_id = %s
        ORDER BY o.created_at DESC
    """, (user_id,))
    
    orders_tuples = cursor.fetchall()
    orders = []
    for order in orders_tuples:
        orders.append({
            'id': order[0],
            'order_number': order[1],
            'user_id': order[2],
            'restaurant_id': order[3],
            'total_amount': safe_float(order[4]),
            'delivery_fee': safe_float(order[5]),
            'discount_amount': safe_float(order[6]),
            'final_amount': safe_float(order[7]),
            'delivery_address': order[8],
            'payment_method': order[9],
            'payment_status': order[10],
            'status': order[11],
            'customer_credit_score': safe_int(order[12]),
            'created_at': order[13],
            'updated_at': order[14],
            'restaurant_name': order[15],
            'trust_badge': bool(order[16])
        })
    
    # Calculate discount
    credit_score = session.get('credit_score', 70)
    discount_percentage = 0
    
    if credit_score >= 90:
        discount_percentage = 20
    elif credit_score >= 75:
        discount_percentage = 15
    elif credit_score >= 50:
        discount_percentage = 10
    elif credit_score >= 30:
        discount_percentage = 5
    
    cursor.close()
    
    return render_template('customer/orders.html',
                         user=user,
                         orders=orders,
                         discount=discount_percentage)

@app.route('/customer/profile')
@login_required('customer')
def customer_profile():
    user_id = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user details
    cursor.execute("""
        SELECT u.*, COUNT(o.id) as total_orders,
               SUM(CASE WHEN o.status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
               SUM(CASE WHEN o.status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_orders
        FROM users u
        LEFT JOIN orders o ON u.id = o.user_id
        WHERE u.id = %s
        GROUP BY u.id
    """, (user_id,))
    
    user_tuple = cursor.fetchone()
    
    if user_tuple:
        user = {
            'id': user_tuple[0],
            'email': user_tuple[1],
            'name': user_tuple[3],
            'phone': user_tuple[4],
            'address': user_tuple[5],
            'role': user_tuple[6],
            'credit_score': user_tuple[7],
            'credit_status': user_tuple[8],
            'total_orders': safe_int(user_tuple[11]),
            'completed_orders': safe_int(user_tuple[12]),
            'cancelled_orders': safe_int(user_tuple[13])
        }
    else:
        user = {}
    
    # Calculate discount
    credit_score = session.get('credit_score', 70)
    discount_percentage = 0
    
    if credit_score >= 90:
        discount_percentage = 20
    elif credit_score >= 75:
        discount_percentage = 15
    elif credit_score >= 50:
        discount_percentage = 10
    elif credit_score >= 30:
        discount_percentage = 5
    
    cursor.close()
    
    return render_template('customer/profile.html',
                         user=user,
                         discount=discount_percentage)

# @app.route('/restaurant/dashboard')
# @login_required('restaurant')
# def restaurant_dashboard():
#     user_id = session['user_id']
    
#     conn = get_db_connection()
#     cursor = conn.cursor()
    
#     # Get restaurant details
#     cursor.execute("""
#         SELECT r.* FROM restaurants r
#         WHERE r.user_id = %s
#     """, (user_id,))
    
#     restaurant_tuple = cursor.fetchone()
    
#     if not restaurant_tuple:
#         flash('Restaurant profile not found', 'error')
#         return redirect(url_for('index'))
    
#     restaurant = {
#         'id': restaurant_tuple[0],
#         'user_id': restaurant_tuple[1],
#         'name': restaurant_tuple[2],
#         'description': restaurant_tuple[3],
#         'address': restaurant_tuple[4],
#         'phone': restaurant_tuple[5],
#         'email': restaurant_tuple[6],
#         'cuisine_type': restaurant_tuple[7],
#         'is_open': bool(restaurant_tuple[10]),
#         'avg_prep_time': safe_int(restaurant_tuple[11]),
#         'rating': safe_float(restaurant_tuple[12]),
#         'trust_badge': bool(restaurant_tuple[14])
#     }
    
#     # Get today's statistics
#     today = datetime.now().date()
#     cursor.execute("""
#         SELECT 
#             COUNT(*) as total_orders,
#             SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
#             SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_orders,
#             SUM(CASE WHEN status = 'completed' THEN final_amount ELSE 0 END) as total_earnings
#         FROM orders 
#         WHERE restaurant_id = %s AND DATE(created_at) = %s
#     """, (restaurant['id'], today))
    
#     stats_tuple = cursor.fetchone()
#     stats = {
#         'total_orders': safe_int(stats_tuple[0] if stats_tuple else 0),
#         'completed_orders': safe_int(stats_tuple[1] if stats_tuple else 0),
#         'cancelled_orders': safe_int(stats_tuple[2] if stats_tuple else 0),
#         'total_earnings': safe_float(stats_tuple[3] if stats_tuple else 0)
#     }
    
#     # Get pending orders
#     cursor.execute("""
#         SELECT o.*, u.name as customer_name, u.credit_score, u.credit_status,
#                TIMESTAMPDIFF(MINUTE, o.created_at, NOW()) as minutes_passed
#         FROM orders o
#         JOIN users u ON o.user_id = u.id
#         WHERE o.restaurant_id = %s AND o.status IN ('pending', 'accepted', 'preparing')
#         ORDER BY o.created_at DESC
#     """, (restaurant['id'],))
    
#     pending_orders_tuples = cursor.fetchall()
#     pending_orders = []
#     for order in pending_orders_tuples:
#         pending_orders.append({
#             'id': order[0],
#             'order_number': order[1],
#             'user_id': order[2],
#             'restaurant_id': order[3],
#             'total_amount': safe_float(order[4]),
#             'delivery_fee': safe_float(order[5]),
#             'discount_amount': safe_float(order[6]),
#             'final_amount': safe_float(order[7]),
#             'status': order[11],
#             'customer_credit_score': safe_int(order[12]),
#             'created_at': order[20],
#             'customer_name': order[24],
#             'credit_score': safe_int(order[25]),
#             'credit_status': order[26],
#             'minutes_passed': safe_int(order[27])
#         })
    
#     # Get menu items
#     cursor.execute("""
#         SELECT * FROM menu_items 
#         WHERE restaurant_id = %s
#         ORDER BY category, name
#     """, (restaurant['id'],))
    
#     menu_items_tuples = cursor.fetchall()
#     menu_items = []
#     for item in menu_items_tuples:
#         menu_items.append({
#             'id': item[0],
#             'restaurant_id': item[1],
#             'name': item[2],
#             'description': item[3],
#             'price': safe_float(item[4]),
#             'category': item[5],
#             'is_available': bool(item[6]),
#             'image_url': item[7],
#             'prep_time': safe_int(item[8]),
#             'created_at': item[9]
#         })
    
#     cursor.close()
    
#     return render_template('restaurant/dashboard.html',
#                          restaurant=restaurant,
#                          stats=stats,
#                          pending_orders=pending_orders,
#                          menu_items=menu_items)




@app.route('/restaurant/dashboard')
@login_required('restaurant')
def restaurant_dashboard():
    user_id = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get restaurant details
    cursor.execute("""
        SELECT r.id, r.user_id, r.name, r.description, r.address, r.phone, 
               r.email, r.cuisine_type, r.is_open, r.avg_prep_time, r.rating, r.trust_badge
        FROM restaurants r
        WHERE r.user_id = %s
    """, (user_id,))
    
    restaurant_tuple = cursor.fetchone()
    
    if not restaurant_tuple:
        flash('Restaurant profile not found', 'error')
        return redirect(url_for('index'))
    
    restaurant = {
        'id': restaurant_tuple[0],
        'user_id': restaurant_tuple[1],
        'name': restaurant_tuple[2],
        'description': restaurant_tuple[3],
        'address': restaurant_tuple[4],
        'phone': restaurant_tuple[5],
        'email': restaurant_tuple[6],
        'cuisine_type': restaurant_tuple[7],
        'is_open': bool(restaurant_tuple[8]),
        'avg_prep_time': safe_int(restaurant_tuple[9]),
        'rating': safe_float(restaurant_tuple[10]),
        'trust_badge': bool(restaurant_tuple[11])
    }
    
    # Get today's statistics
    today = datetime.now().date()
    cursor.execute("""
        SELECT 
            COUNT(*) as total_orders,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
            SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_orders,
            SUM(CASE WHEN status = 'completed' THEN final_amount ELSE 0 END) as total_earnings
        FROM orders 
        WHERE restaurant_id = %s AND DATE(created_at) = %s
    """, (restaurant['id'], today))
    
    stats_tuple = cursor.fetchone()
    stats = {
        'total_orders': safe_int(stats_tuple[0] if stats_tuple else 0),
        'completed_orders': safe_int(stats_tuple[1] if stats_tuple else 0),
        'cancelled_orders': safe_int(stats_tuple[2] if stats_tuple else 0),
        'total_earnings': safe_float(stats_tuple[3] if stats_tuple else 0)
    }
    
    # Get pending orders - FIXED: Simplified query
    cursor.execute("""
        SELECT o.id, o.order_number, o.user_id, o.restaurant_id, o.total_amount,
               o.delivery_fee, o.discount_amount, o.final_amount, o.delivery_address,
               o.payment_method, o.payment_status, o.status, o.customer_credit_score,
               o.created_at, u.name as customer_name, u.credit_score, u.credit_status
        FROM orders o
        JOIN users u ON o.user_id = u.id
        WHERE o.restaurant_id = %s AND o.status IN ('pending', 'accepted', 'preparing')
        ORDER BY o.created_at DESC
    """, (restaurant['id'],))
    
    pending_orders_tuples = cursor.fetchall()
    pending_orders = []
    for order in pending_orders_tuples:
        pending_orders.append({
            'id': order[0],
            'order_number': order[1],
            'user_id': order[2],
            'restaurant_id': order[3],
            'total_amount': safe_float(order[4]),
            'delivery_fee': safe_float(order[5]),
            'discount_amount': safe_float(order[6]),
            'final_amount': safe_float(order[7]),
            'status': order[11],
            'customer_credit_score': safe_int(order[12]),
            'created_at': order[13],
            'customer_name': order[14],
            'credit_score': safe_int(order[15]),
            'credit_status': order[16]
        })
    
    # Get menu items
    cursor.execute("""
        SELECT id, restaurant_id, name, description, price, category, 
               is_available, image_url, prep_time, created_at
        FROM menu_items 
        WHERE restaurant_id = %s
        ORDER BY category, name
    """, (restaurant['id'],))
    
    menu_items_tuples = cursor.fetchall()
    menu_items = []
    for item in menu_items_tuples:
        menu_items.append({
            'id': item[0],
            'restaurant_id': item[1],
            'name': item[2],
            'description': item[3],
            'price': safe_float(item[4]),
            'category': item[5],
            'is_available': bool(item[6]),
            'image_url': item[7],
            'prep_time': safe_int(item[8]),
            'created_at': item[9]
        })
    
    cursor.close()
    
    return render_template('restaurant/dashboard.html',
                         restaurant=restaurant,
                         stats=stats,
                         pending_orders=pending_orders,
                         menu_items=menu_items)



# @app.route('/restaurant/orders')
# @login_required('restaurant')
# def restaurant_orders():
#     user_id = session['user_id']
    
#     conn = get_db_connection()
#     cursor = conn.cursor()
    
#     # Get restaurant details
#     cursor.execute("SELECT id FROM restaurants WHERE user_id = %s", (user_id,))
#     restaurant_tuple = cursor.fetchone()
    
#     if not restaurant_tuple:
#         flash('Restaurant profile not found', 'error')
#         return redirect(url_for('index'))
    
#     restaurant = {'id': restaurant_tuple[0]}
    
#     # Get all orders for this restaurant
#     cursor.execute("""
#         SELECT o.*, u.name as customer_name, u.credit_score, u.credit_status,
#                COUNT(oi.id) as item_count
#         FROM orders o
#         JOIN users u ON o.user_id = u.id
#         LEFT JOIN order_items oi ON o.id = oi.order_id
#         WHERE o.restaurant_id = %s
#         GROUP BY o.id
#         ORDER BY o.created_at DESC
#     """, (restaurant['id'],))
    
#     orders_tuples = cursor.fetchall()
#     orders = []
#     for order in orders_tuples:
#         orders.append({
#             'id': order[0],
#             'order_number': order[1],
#             'user_id': order[2],
#             'restaurant_id': order[3],
#             'total_amount': safe_float(order[4]),
#             'delivery_fee': safe_float(order[5]),
#             'discount_amount': safe_float(order[6]),
#             'final_amount': safe_float(order[7]),
#             'delivery_address': order[8],
#             'payment_method': order[9],
#             'payment_status': order[10],
#             'status': order[11],
#             'customer_credit_score': safe_int(order[12]),
#             'created_at': order[20],
#             'customer_name': order[24],
#             'credit_score': safe_int(order[25]),
#             'credit_status': order[26],
#             'item_count': safe_int(order[27])
#         })
    
#     cursor.close()
    
#     return render_template('restaurant/orders.html',
#                          restaurant=restaurant,
#                          orders=orders)



@app.route('/restaurant/orders')
@login_required('restaurant')
def restaurant_orders():
    user_id = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get restaurant details
    cursor.execute("SELECT id, name FROM restaurants WHERE user_id = %s", (user_id,))
    restaurant_tuple = cursor.fetchone()
    
    if not restaurant_tuple:
        flash('Restaurant profile not found', 'error')
        return redirect(url_for('index'))
    
    restaurant = {
        'id': restaurant_tuple[0],
        'name': restaurant_tuple[1],
        'user_id': user_id
    }
    
    # Get user details for the template
    cursor.execute("SELECT id, email, name, phone, role FROM users WHERE id = %s", (user_id,))
    user_tuple = cursor.fetchone()
    
    if user_tuple:
        user = {
            'id': user_tuple[0],
            'email': user_tuple[1],
            'name': user_tuple[2],
            'phone': user_tuple[3],
            'role': user_tuple[4]
        }
    else:
        user = {}
    
    # Get all orders for this restaurant - FIXED: Simplified query
    cursor.execute("""
        SELECT o.id, o.order_number, o.user_id, o.restaurant_id, o.total_amount,
               o.delivery_fee, o.discount_amount, o.final_amount, o.delivery_address,
               o.payment_method, o.payment_status, o.status, o.customer_credit_score,
               o.created_at, u.name as customer_name, u.credit_score, u.credit_status
        FROM orders o
        JOIN users u ON o.user_id = u.id
        WHERE o.restaurant_id = %s
        ORDER BY o.created_at DESC
    """, (restaurant['id'],))
    
    orders_tuples = cursor.fetchall()
    orders = []
    for order in orders_tuples:
        orders.append({
            'id': order[0],
            'order_number': order[1],
            'user_id': order[2],
            'restaurant_id': order[3],
            'total_amount': safe_float(order[4]),
            'delivery_fee': safe_float(order[5]),
            'discount_amount': safe_float(order[6]),
            'final_amount': safe_float(order[7]),
            'delivery_address': order[8],
            'payment_method': order[9],
            'payment_status': order[10],
            'status': order[11],
            'customer_credit_score': safe_int(order[12]),
            'created_at': order[13],
            'customer_name': order[14],
            'credit_score': safe_int(order[15]),
            'credit_status': order[16]
        })
    
    cursor.close()
    
    return render_template('restaurant/orders.html',
                         restaurant=restaurant,
                         user=user,
                         orders=orders)




@app.route('/restaurant/menu')
@login_required('restaurant')
def restaurant_menu():
    user_id = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get restaurant details
    cursor.execute("SELECT * FROM restaurants WHERE user_id = %s", (user_id,))
    restaurant_tuple = cursor.fetchone()
    
    if not restaurant_tuple:
        flash('Restaurant profile not found', 'error')
        return redirect(url_for('index'))
    
    restaurant = {
        'id': restaurant_tuple[0],
        'user_id': restaurant_tuple[1],
        'name': restaurant_tuple[2],
        'description': restaurant_tuple[3],
        'address': restaurant_tuple[4],
        'phone': restaurant_tuple[5],
        'email': restaurant_tuple[6],
        'cuisine_type': restaurant_tuple[7],
        'is_open': bool(restaurant_tuple[10]),
        'avg_prep_time': safe_int(restaurant_tuple[11]),
        'rating': safe_float(restaurant_tuple[12]),
        'trust_badge': bool(restaurant_tuple[14])
    }
    
    # Get menu items
    cursor.execute("""
        SELECT * FROM menu_items 
        WHERE restaurant_id = %s
        ORDER BY category, name
    """, (restaurant['id'],))
    
    menu_items_tuples = cursor.fetchall()
    menu_items = []
    for item in menu_items_tuples:
        menu_items.append({
            'id': item[0],
            'restaurant_id': item[1],
            'name': item[2],
            'description': item[3],
            'price': safe_float(item[4]),
            'category': item[5],
            'is_available': bool(item[6]),
            'image_url': item[7],
            'prep_time': safe_int(item[8]),
            'created_at': item[9]
        })
    
    cursor.close()
    
    return render_template('restaurant/menu.html',
                         restaurant=restaurant,
                         menu_items=menu_items)

@app.route('/restaurant/feedback')
@login_required('restaurant')
def restaurant_feedback():
    user_id = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get restaurant details
    cursor.execute("SELECT * FROM restaurants WHERE user_id = %s", (user_id,))
    restaurant_tuple = cursor.fetchone()
    
    if not restaurant_tuple:
        flash('Restaurant profile not found', 'error')
        return redirect(url_for('index'))
    
    restaurant = {
        'id': restaurant_tuple[0],
        'user_id': restaurant_tuple[1],
        'name': restaurant_tuple[2],
        'description': restaurant_tuple[3],
        'address': restaurant_tuple[4],
        'phone': restaurant_tuple[5],
        'email': restaurant_tuple[6],
        'cuisine_type': restaurant_tuple[7],
        'is_open': bool(restaurant_tuple[10]),
        'avg_prep_time': safe_int(restaurant_tuple[11]),
        'rating': safe_float(restaurant_tuple[12]),
        'trust_badge': bool(restaurant_tuple[14])
    }
    
    cursor.close()
    
    return render_template('restaurant/feedback.html',
                         restaurant=restaurant)

@app.route('/admin/dashboard')
@login_required('admin')
def admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get system statistics
    cursor.execute("""
        SELECT 
            (SELECT COUNT(*) FROM users WHERE role = 'customer') as total_customers,
            (SELECT COUNT(*) FROM users WHERE role = 'restaurant') as total_restaurants,
            (SELECT COUNT(*) FROM orders WHERE DATE(created_at) = CURDATE()) as today_orders,
            (SELECT COALESCE(SUM(final_amount), 0) FROM orders WHERE DATE(created_at) = CURDATE() AND status = 'completed') as today_revenue,
            (SELECT COUNT(*) FROM users WHERE credit_status = 'trusted') as trusted_users,
            (SELECT COUNT(*) FROM users WHERE credit_status = 'risky') as risky_users,
            (SELECT COUNT(*) FROM users WHERE credit_status = 'blocked') as blocked_users,
            (SELECT COALESCE(SUM(discount_amount), 0) FROM orders WHERE DATE(created_at) = CURDATE()) as total_discounts,
            (SELECT COALESCE(SUM(delivery_fee), 0) FROM orders WHERE DATE(created_at) = CURDATE()) as total_delivery_fees,
            (SELECT COALESCE(SUM(o.final_amount * r.commission_rate / 100), 0) 
             FROM orders o 
             JOIN restaurants r ON o.restaurant_id = r.id 
             WHERE DATE(o.created_at) = CURDATE() AND o.status = 'completed') as total_commission
    """)
    
    stats_tuple = cursor.fetchone()
    stats = {
        'total_customers': safe_int(stats_tuple[0] if stats_tuple else 0),
        'total_restaurants': safe_int(stats_tuple[1] if stats_tuple else 0),
        'today_orders': safe_int(stats_tuple[2] if stats_tuple else 0),
        'today_revenue': safe_float(stats_tuple[3] if stats_tuple else 0),
        'trusted_users': safe_int(stats_tuple[4] if stats_tuple else 0),
        'risky_users': safe_int(stats_tuple[5] if stats_tuple else 0),
        'blocked_users': safe_int(stats_tuple[6] if stats_tuple else 0),
        'total_discounts': safe_float(stats_tuple[7] if stats_tuple else 0),
        'total_delivery_fees': safe_float(stats_tuple[8] if stats_tuple else 0),
        'total_commission': safe_float(stats_tuple[9] if stats_tuple else 0)
    }
    
    # Get recent orders
    cursor.execute("""
        SELECT o.*, u.name as customer_name, r.name as restaurant_name,
               u.credit_score, u.credit_status
        FROM orders o
        JOIN users u ON o.user_id = u.id
        JOIN restaurants r ON o.restaurant_id = r.id
        ORDER BY o.created_at DESC
        LIMIT 20
    """)
    
    recent_orders_tuples = cursor.fetchall()
    recent_orders = []
    for order in recent_orders_tuples:
        recent_orders.append({
            'id': order[0],
            'order_number': order[1],
            'user_id': order[2],
            'restaurant_id': order[3],
            'total_amount': safe_float(order[4]),
            'delivery_fee': safe_float(order[5]),
            'discount_amount': safe_float(order[6]),
            'final_amount': safe_float(order[7]),
            'delivery_address': order[8],
            'payment_method': order[9],
            'payment_status': order[10],
            'status': order[11],
            'customer_credit_score': safe_int(order[12]),
            'created_at': order[20],
            'customer_name': order[24],
            'restaurant_name': order[25],
            'credit_score': safe_int(order[26]),
            'credit_status': order[27]
        })
    
    # Get users by credit status
    cursor.execute("""
        SELECT u.*, 
               COUNT(o.id) as total_orders,
               SUM(CASE WHEN o.status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_orders
        FROM users u
        LEFT JOIN orders o ON u.id = o.user_id
        WHERE u.role = 'customer'
        GROUP BY u.id
        ORDER BY u.credit_score DESC
        LIMIT 50
    """)
    
    users_tuples = cursor.fetchall()
    users = []
    for user in users_tuples:
        users.append({
            'id': user[0],
            'email': user[1],
            'name': user[3],
            'phone': user[4],
            'address': user[5],
            'role': user[6],
            'credit_score': safe_int(user[7]),
            'credit_status': user[8],
            'created_at': user[9],
            'is_active': bool(user[11]),
            'total_orders': safe_int(user[12]),
            'cancelled_orders': safe_int(user[13])
        })
    
    cursor.close()
    
    return render_template('admin/dashboard.html',
                         stats=stats,
                         orders=recent_orders,
                         users=users,
                         credit_ranges=Config.CREDIT_SCORE_RANGES)

@app.route('/admin/users')
@login_required('admin')
def admin_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all users
    cursor.execute("""
        SELECT u.*, 
               COUNT(o.id) as total_orders,
               SUM(CASE WHEN o.status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_orders
        FROM users u
        LEFT JOIN orders o ON u.id = o.user_id
        GROUP BY u.id
        ORDER BY u.created_at DESC
    """)
    
    users_tuples = cursor.fetchall()
    users = []
    for user in users_tuples:
        users.append({
            'id': user[0],
            'email': user[1],
            'name': user[3],
            'phone': user[4],
            'address': user[5],
            'role': user[6],
            'credit_score': safe_int(user[7]),
            'credit_status': user[8],
            'created_at': user[9],
            'is_active': bool(user[11]),
            'total_orders': safe_int(user[12]),
            'cancelled_orders': safe_int(user[13])
        })
    
    cursor.close()
    
    return render_template('admin/users.html', users=users)

# @app.route('/admin/restaurants')
# @login_required('admin')
# def admin_restaurants():
#     conn = get_db_connection()
#     cursor = conn.cursor()
    
#     # Get all restaurants with owner info
#     cursor.execute("""
#         SELECT r.*, u.name as owner_name, u.email as owner_email,
#                COUNT(o.id) as total_orders,
#                AVG(o.restaurant_feedback) as avg_rating
#         FROM restaurants r
#         JOIN users u ON r.user_id = u.id
#         LEFT JOIN orders o ON r.id = o.restaurant_id
#         GROUP BY r.id
#         ORDER BY r.created_at DESC
#     """)
    
#     restaurants_tuples = cursor.fetchall()
#     restaurants = []
#     for rest in restaurants_tuples:
#         restaurants.append({
#             'id': rest[0],
#             'user_id': rest[1],
#             'name': rest[2],
#             'description': rest[3],
#             'address': rest[4],
#             'phone': rest[5],
#             'email': rest[6],
#             'cuisine_type': rest[7],
#             'is_open': bool(rest[10]),
#             'avg_prep_time': safe_int(rest[11]),
#             'rating': safe_float(rest[12]),
#             'trust_badge': bool(rest[14]),
#             'created_at': rest[20],
#             'owner_name': rest[21],
#             'owner_email': rest[22],
#             'total_orders': safe_int(rest[23]),
#             'avg_rating': safe_float(rest[24])
#         })
    
#     cursor.close()
    
#     return render_template('admin/restaurants.html', restaurants=restaurants)


@app.route('/admin/restaurants')
@login_required('admin')
def admin_restaurants():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all restaurants with owner info - FIXED: Simplified query
    cursor.execute("""
        SELECT r.id, r.user_id, r.name, r.description, r.address, r.phone, 
               r.email, r.cuisine_type, r.is_open, r.avg_prep_time, r.rating,
               r.trust_badge, r.created_at, u.name as owner_name, u.email as owner_email
        FROM restaurants r
        JOIN users u ON r.user_id = u.id
        ORDER BY r.created_at DESC
    """)
    
    restaurants_tuples = cursor.fetchall()
    restaurants = []
    for rest in restaurants_tuples:
        restaurants.append({
            'id': rest[0],
            'user_id': rest[1],
            'name': rest[2],
            'description': rest[3],
            'address': rest[4],
            'phone': rest[5],
            'email': rest[6],
            'cuisine_type': rest[7],
            'is_open': bool(rest[8]),
            'avg_prep_time': safe_int(rest[9]),
            'rating': safe_float(rest[10]),
            'trust_badge': bool(rest[11]),
            'created_at': rest[12],
            'owner_name': rest[13],
            'owner_email': rest[14]
        })
    
    cursor.close()
    
    return render_template('admin/restaurants.html', restaurants=restaurants)




@app.route('/admin/analytics')
@login_required('admin')
def admin_analytics():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get analytics data
    cursor.execute("""
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as orders,
            COALESCE(SUM(final_amount), 0) as revenue,
            COALESCE(AVG(customer_credit_score), 0) as avg_credit_score
        FROM orders
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY DATE(created_at)
        ORDER BY date DESC
    """)
    
    daily_stats_tuples = cursor.fetchall()
    daily_stats = []
    for stat in daily_stats_tuples:
        daily_stats.append({
            'date': stat[0],
            'orders': safe_int(stat[1]),
            'revenue': safe_float(stat[2]),
            'avg_credit_score': safe_float(stat[3])
        })
    
    # Get credit score distribution
    cursor.execute("""
        SELECT 
            credit_status,
            COUNT(*) as count
        FROM users
        WHERE role = 'customer'
        GROUP BY credit_status
    """)
    
    credit_distribution_tuples = cursor.fetchall()
    credit_distribution = []
    for dist in credit_distribution_tuples:
        credit_distribution.append({
            'credit_status': dist[0],
            'count': safe_int(dist[1])
        })
    
    cursor.close()
    
    return render_template('admin/analytics.html',
                         daily_stats=daily_stats,
                         credit_distribution=credit_distribution)

# API Routes
@app.route('/api/update_order_status', methods=['POST'])
@login_required('restaurant')
def update_order_status():
    order_id = request.json.get('order_id')
    status = request.json.get('status')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get order details
        cursor.execute("""
            SELECT o.user_id, o.order_number, o.customer_credit_score
            FROM orders o
            WHERE o.id = %s
        """, (order_id,))
        
        order = cursor.fetchone()
        
        if not order:
            return jsonify({'success': False, 'message': 'Order not found'})
        
        # Update order status
        cursor.execute("""
            UPDATE orders 
            SET status = %s, 
                updated_at = %s
            WHERE id = %s
        """, (status, datetime.now(), order_id))
        
        # Add notification for customer
        status_messages = {
            'accepted': 'Your order has been accepted by the restaurant.',
            'preparing': 'Your food is being prepared.',
            'ready': 'Your order is ready for pickup/delivery.',
            'cancelled': 'Your order has been cancelled by the restaurant.'
        }
        
        if status in status_messages:
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, type)
                VALUES (%s, 'Order Update', %s, 'info')
            """, (order[0], status_messages[status]))
        
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Order status updated'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()

@app.route('/api/submit_customer_feedback', methods=['POST'])
@login_required('restaurant')
def submit_customer_feedback():
    data = request.json
    order_id = data.get('order_id')
    politeness = safe_int(data.get('politeness', 0))
    punctuality = safe_int(data.get('punctuality', 0))
    authenticity = safe_int(data.get('authenticity', 0))
    comments = data.get('comments', '')
    
    user_id = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get restaurant ID
        cursor.execute("SELECT id FROM restaurants WHERE user_id = %s", (user_id,))
        restaurant = cursor.fetchone()
        
        if not restaurant:
            return jsonify({'success': False, 'message': 'Restaurant not found'})
        
        restaurant_id = restaurant[0]
        
        # Get order details
        cursor.execute("SELECT user_id FROM orders WHERE id = %s", (order_id,))
        order = cursor.fetchone()
        
        if not order:
            return jsonify({'success': False, 'message': 'Order not found'})
        
        customer_id = order[0]
        
        # Calculate overall rating
        overall = (politeness + punctuality + authenticity) / 3
        
        # Insert feedback
        cursor.execute("""
            INSERT INTO customer_feedback 
            (restaurant_id, user_id, order_id, politeness_rating, 
             pickup_punctuality, order_authenticity, overall_rating, comments)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (restaurant_id, customer_id, order_id, politeness, punctuality, authenticity, overall, comments))
        
        # Update user's credit score
        new_score = update_user_credit_score(customer_id)
        
        # Add to credit history
        cursor.execute("""
            INSERT INTO credit_history 
            (user_id, old_score, new_score, change_amount, reason, triggered_by, reference_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (customer_id, session.get('credit_score', 70), new_score, 
              new_score - session.get('credit_score', 70), 
              'Restaurant feedback', 'restaurant', order_id))
        
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Feedback submitted successfully'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()

@app.route('/api/admin/update_credit_score', methods=['POST'])
@login_required('admin')
def admin_update_credit_score():
    user_id = request.json.get('user_id')
    new_score = safe_int(request.json.get('score', 70))
    reason = request.json.get('reason', 'Manual adjustment by admin')
    
    admin_id = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get current score
        cursor.execute("SELECT credit_score FROM users WHERE id = %s", (user_id,))
        current = cursor.fetchone()
        
        if not current:
            return jsonify({'success': False, 'message': 'User not found'})
        
        old_score = safe_int(current[0])
        
        # Update user score
        cursor.execute("""
            UPDATE users 
            SET credit_score = %s,
                credit_status = CASE 
                    WHEN %s >= 90 THEN 'trusted'
                    WHEN %s >= 75 THEN 'good'
                    WHEN %s >= 50 THEN 'average'
                    WHEN %s >= 30 THEN 'risky'
                    ELSE 'blocked'
                END,
                last_credit_update = %s
            WHERE id = %s
        """, (new_score, new_score, new_score, new_score, new_score, datetime.now(), user_id))
        
        # Add to credit history
        cursor.execute("""
            INSERT INTO credit_history 
            (user_id, old_score, new_score, change_amount, reason, triggered_by)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, old_score, new_score, new_score - old_score, reason, 'admin'))
        
        # Log admin action
        cursor.execute("""
            INSERT INTO admin_actions 
            (admin_id, action_type, target_type, target_id, details, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (admin_id, 'update_credit_score', 'user', user_id, 
              f'Updated credit score from {old_score} to {new_score}. Reason: {reason}', 
              request.remote_addr))
        
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Credit score updated successfully'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()

@app.route('/api/search_restaurants')
def search_restaurants():
    query = request.args.get('q', '')
    cuisine = request.args.get('cuisine', '')
    min_rating = safe_float(request.args.get('min_rating', 0))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    sql = """
        SELECT r.*, 
               COUNT(DISTINCT o.id) as total_orders,
               AVG(TIMESTAMPDIFF(MINUTE, o.created_at, o.actual_delivery_time)) as avg_delivery_time
        FROM restaurants r
        LEFT JOIN orders o ON r.id = o.restaurant_id AND o.status = 'completed'
        WHERE r.is_open = TRUE
    """
    
    params = []
    
    if query:
        sql += " AND (r.name LIKE %s OR r.description LIKE %s OR r.cuisine_type LIKE %s)"
        params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])
    
    if cuisine:
        sql += " AND r.cuisine_type = %s"
        params.append(cuisine)
    
    if min_rating > 0:
        sql += " AND r.rating >= %s"
        params.append(min_rating)
    
    sql += " GROUP BY r.id ORDER BY r.trust_badge DESC, r.rating DESC"
    
    cursor.execute(sql, tuple(params))
    restaurants_tuples = cursor.fetchall()
    
    restaurants = []
    for rest in restaurants_tuples:
        restaurants.append({
            'id': rest[0],
            'user_id': rest[1],
            'name': rest[2],
            'description': rest[3],
            'address': rest[4],
            'phone': rest[5],
            'email': rest[6],
            'cuisine_type': rest[7],
            'is_open': bool(rest[10]),
            'avg_prep_time': safe_int(rest[11]),
            'rating': safe_float(rest[12]),
            'trust_badge': bool(rest[14]),
            'total_orders': safe_int(rest[24]),
            'avg_delivery_time': safe_float(rest[25])
        })
    
    cursor.close()
    
    return jsonify({'restaurants': restaurants})

@app.route('/api/get_menu/<int:restaurant_id>')
def get_menu(restaurant_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM menu_items 
        WHERE restaurant_id = %s AND is_available = TRUE
        ORDER BY category, name
    """, (restaurant_id,))
    
    menu_items_tuples = cursor.fetchall()
    menu_items = []
    for item in menu_items_tuples:
        menu_items.append({
            'id': item[0],
            'restaurant_id': item[1],
            'name': item[2],
            'description': item[3],
            'price': safe_float(item[4]),
            'category': item[5],
            'is_available': bool(item[6]),
            'image_url': item[7],
            'prep_time': safe_int(item[8]),
            'created_at': item[9]
        })
    
    cursor.close()
    
    return jsonify({'menu': menu_items})

@app.route('/api/create_order', methods=['POST'])
@login_required('customer')
def create_order():
    user_id = session['user_id']
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get user's current credit score
        cursor.execute("SELECT credit_score FROM users WHERE id = %s", (user_id,))
        credit_score_result = cursor.fetchone()
        credit_score = safe_int(credit_score_result[0] if credit_score_result else 70)
        
        # Calculate discount based on credit score
        discount_percentage = 0
        if credit_score >= 90:
            discount_percentage = 20
        elif credit_score >= 75:
            discount_percentage = 15
        elif credit_score >= 50:
            discount_percentage = 10
        elif credit_score >= 30:
            discount_percentage = 5
        
        # Calculate totals
        total_amount = 0
        for item in data['items']:
            cursor.execute("SELECT price FROM menu_items WHERE id = %s", (item['id'],))
            price_result = cursor.fetchone()
            price = safe_float(price_result[0] if price_result else 0)
            total_amount += price * item['quantity']
        
        delivery_fee = 30  # Fixed delivery fee for now
        discount_amount = total_amount * discount_percentage / 100
        final_amount = total_amount + delivery_fee - discount_amount
        
        # Generate order number
        order_number = generate_order_id()
        
        # Create order
        cursor.execute("""
            INSERT INTO orders 
            (order_number, user_id, restaurant_id, total_amount, delivery_fee, 
             discount_amount, final_amount, delivery_address, payment_method, 
             payment_status, customer_credit_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (order_number, user_id, data['restaurant_id'], total_amount, delivery_fee,
              discount_amount, final_amount, data['address'], data['payment_method'],
              'completed', credit_score))
        
        order_id = cursor.lastrowid
        
        # Add order items
        for item in data['items']:
            cursor.execute("SELECT price FROM menu_items WHERE id = %s", (item['id'],))
            price_result = cursor.fetchone()
            price = safe_float(price_result[0] if price_result else 0)
            
            cursor.execute("""
                INSERT INTO order_items (order_id, menu_item_id, quantity, price)
                VALUES (%s, %s, %s, %s)
            """, (order_id, item['id'], item['quantity'], price))
        
        # Add notification for restaurant
        cursor.execute("SELECT user_id FROM restaurants WHERE id = %s", (data['restaurant_id'],))
        restaurant_user = cursor.fetchone()
        
        if restaurant_user:
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, type)
                VALUES (%s, 'New Order', %s, 'info')
            """, (restaurant_user[0], f'You have a new order #{order_number}'))
        
        conn.commit()
        
        return jsonify({
            'success': True, 
            'order_id': order_id,
            'order_number': order_number,
            'message': 'Order placed successfully',
            'discount_applied': discount_amount
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()

@app.route('/api/cancel_order', methods=['POST'])
@login_required()
def cancel_order():
    order_id = request.json.get('order_id')
    reason = request.json.get('reason', '')
    
    user_id = session['user_id']
    role = session['role']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get order details
        cursor.execute("""
            SELECT user_id, restaurant_id, status, customer_credit_score
            FROM orders WHERE id = %s
        """, (order_id,))
        
        order = cursor.fetchone()
        
        if not order:
            return jsonify({'success': False, 'message': 'Order not found'})
        
        # Check permissions
        if role != 'admin' and order[0] != user_id:
            # Check if user is restaurant owner
            cursor.execute("SELECT user_id FROM restaurants WHERE id = %s", (order[1],))
            restaurant_owner = cursor.fetchone()
            
            if not restaurant_owner or restaurant_owner[0] != user_id:
                return jsonify({'success': False, 'message': 'Unauthorized'})
        
        # Update order status
        cursor.execute("""
            UPDATE orders 
            SET status = 'cancelled',
                cancelled_by = %s,
                cancellation_reason = %s,
                updated_at = %s
            WHERE id = %s
        """, (role, reason, datetime.now(), order_id))
        
        # Update user's credit score if cancelled by customer
        if role == 'customer':
            new_score = update_user_credit_score(order[0])
            
            # Add to credit history
            cursor.execute("""
                INSERT INTO credit_history 
                (user_id, old_score, new_score, change_amount, reason, triggered_by, reference_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (order[0], safe_int(order[3]), new_score, new_score - safe_int(order[3]), 
                  f'Order cancellation: {reason}', 'system', order_id))
            
            # Add warning notification
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, type)
                VALUES (%s, 'Credit Score Impact', %s, 'warning')
            """, (order[0], f'Your credit score has been affected due to order cancellation. Reason: {reason}'))
        
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Order cancelled successfully'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()

@app.route('/api/get_user_stats')
@login_required()
def get_user_stats():
    user_id = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            u.credit_score,
            u.credit_status,
            COUNT(o.id) as total_orders,
            SUM(CASE WHEN o.status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
            SUM(CASE WHEN o.status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_orders,
            AVG(CASE WHEN cf.order_id IS NOT NULL THEN cf.overall_rating END) as avg_feedback
        FROM users u
        LEFT JOIN orders o ON u.id = o.user_id
        LEFT JOIN customer_feedback cf ON o.id = cf.order_id
        WHERE u.id = %s
        GROUP BY u.id
    """, (user_id,))
    
    stats_tuple = cursor.fetchone()
    stats = {
        'credit_score': safe_int(stats_tuple[0] if stats_tuple else 70),
        'credit_status': stats_tuple[1] if stats_tuple and stats_tuple[1] else 'average',
        'total_orders': safe_int(stats_tuple[2] if stats_tuple else 0),
        'completed_orders': safe_int(stats_tuple[3] if stats_tuple else 0),
        'cancelled_orders': safe_int(stats_tuple[4] if stats_tuple else 0),
        'avg_feedback': safe_float(stats_tuple[5] if stats_tuple else 0)
    }
    
    # Get credit history
    cursor.execute("""
        SELECT * FROM credit_history 
        WHERE user_id = %s 
        ORDER BY created_at DESC 
        LIMIT 10
    """, (user_id,))
    
    history_tuples = cursor.fetchall()
    history = []
    for hist in history_tuples:
        history.append({
            'id': hist[0],
            'user_id': hist[1],
            'old_score': safe_int(hist[2]),
            'new_score': safe_int(hist[3]),
            'change_amount': safe_int(hist[4]),
            'reason': hist[5],
            'triggered_by': hist[6],
            'reference_id': safe_int(hist[7]),
            'created_at': hist[8]
        })
    
    cursor.close()
    
    return jsonify({'stats': stats, 'history': history})

# Additional API endpoints for restaurant
@app.route('/api/pending_feedback')
@login_required('restaurant')
def pending_feedback():
    user_id = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get restaurant ID
    cursor.execute("SELECT id FROM restaurants WHERE user_id = %s", (user_id,))
    restaurant = cursor.fetchone()
    
    if not restaurant:
        return jsonify({'success': False, 'message': 'Restaurant not found'})
    
    restaurant_id = restaurant[0]
    
    # Get orders pending feedback
    cursor.execute("""
        SELECT o.*, u.name as customer_name, u.credit_score, u.credit_status
        FROM orders o
        JOIN users u ON o.user_id = u.id
        LEFT JOIN customer_feedback cf ON o.id = cf.order_id
        WHERE o.restaurant_id = %s 
          AND o.status = 'completed'
          AND cf.id IS NULL
        ORDER BY o.created_at DESC
        LIMIT 10
    """, (restaurant_id,))
    
    orders_tuples = cursor.fetchall()
    orders = []
    for order in orders_tuples:
        orders.append({
            'id': order[0],
            'order_number': order[1],
            'user_id': order[2],
            'restaurant_id': order[3],
            'total_amount': safe_float(order[4]),
            'delivery_fee': safe_float(order[5]),
            'discount_amount': safe_float(order[6]),
            'final_amount': safe_float(order[7]),
            'status': order[11],
            'customer_credit_score': safe_int(order[12]),
            'created_at': order[20],
            'customer_name': order[24],
            'credit_score': safe_int(order[25]),
            'credit_status': order[26]
        })
    
    cursor.close()
    
    return jsonify({'success': True, 'orders': orders})

@app.route('/api/feedback_history')
@login_required('restaurant')
def feedback_history():
    user_id = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get restaurant ID
    cursor.execute("SELECT id FROM restaurants WHERE user_id = %s", (user_id,))
    restaurant = cursor.fetchone()
    
    if not restaurant:
        return jsonify({'success': False, 'message': 'Restaurant not found'})
    
    restaurant_id = restaurant[0]
    
    # Get feedback history
    cursor.execute("""
        SELECT cf.*, o.order_number, u.name as customer_name,
               ch.change_amount as credit_change
        FROM customer_feedback cf
        JOIN orders o ON cf.order_id = o.id
        JOIN users u ON cf.user_id = u.id
        LEFT JOIN credit_history ch ON cf.order_id = ch.reference_id AND ch.triggered_by = 'restaurant'
        WHERE cf.restaurant_id = %s
        ORDER BY cf.created_at DESC
        LIMIT 20
    """, (restaurant_id,))
    
    feedback_tuples = cursor.fetchall()
    feedback = []
    for fb in feedback_tuples:
        feedback.append({
            'id': fb[0],
            'restaurant_id': fb[1],
            'user_id': fb[2],
            'order_id': fb[3],
            'politeness_rating': safe_int(fb[4]),
            'pickup_punctuality': safe_int(fb[5]),
            'order_authenticity': safe_int(fb[6]),
            'overall_rating': safe_float(fb[7]),
            'comments': fb[8],
            'created_at': fb[9],
            'order_number': fb[10],
            'customer_name': fb[11],
            'credit_change': safe_int(fb[12])
        })
    
    cursor.close()
    
    return jsonify({'success': True, 'feedback': feedback})

@app.route('/api/feedback_stats')
@login_required('restaurant')
def feedback_stats():
    user_id = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get restaurant ID
    cursor.execute("SELECT id FROM restaurants WHERE user_id = %s", (user_id,))
    restaurant = cursor.fetchone()
    
    if not restaurant:
        return jsonify({'success': False, 'message': 'Restaurant not found'})
    
    restaurant_id = restaurant[0]
    
    # Get total completed orders
    cursor.execute("""
        SELECT COUNT(*) as total_completed 
        FROM orders 
        WHERE restaurant_id = %s AND status = 'completed'
    """, (restaurant_id,))
    
    total_completed_result = cursor.fetchone()
    total_completed = safe_int(total_completed_result[0] if total_completed_result else 0)
    
    # Get feedback statistics
    cursor.execute("""
        SELECT 
            COALESCE(AVG(overall_rating), 0) as average_rating,
            COUNT(*) as total_feedback,
            SUM(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) THEN 1 ELSE 0 END) as monthly_feedback
        FROM customer_feedback
        WHERE restaurant_id = %s
    """, (restaurant_id,))
    
    stats_tuple = cursor.fetchone()
    
    if stats_tuple:
        average_rating = safe_float(stats_tuple[0])
        total_feedback = safe_int(stats_tuple[1])
        monthly_feedback = safe_int(stats_tuple[2])
    else:
        average_rating = 0
        total_feedback = 0
        monthly_feedback = 0
    
    # Calculate response rate
    if total_completed > 0:
        response_rate = (total_feedback * 100.0 / total_completed)
    else:
        response_rate = 0
    
    stats = {
        'average_rating': round(average_rating, 2),
        'total_feedback': total_feedback,
        'monthly_feedback': monthly_feedback,
        'response_rate': round(response_rate, 2)
    }
    
    cursor.close()
    
    return jsonify({'success': True, **stats})

# Restaurant menu management API
@app.route('/api/add_menu_item', methods=['POST'])
@login_required('restaurant')
def add_menu_item():
    user_id = session['user_id']
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get restaurant ID
        cursor.execute("SELECT id FROM restaurants WHERE user_id = %s", (user_id,))
        restaurant = cursor.fetchone()
        
        if not restaurant:
            return jsonify({'success': False, 'message': 'Restaurant not found'})
        
        restaurant_id = restaurant[0]
        
        # Insert menu item
        cursor.execute("""
            INSERT INTO menu_items 
            (restaurant_id, name, description, price, category, is_available, prep_time, image_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (restaurant_id, data.get('name'), data.get('description'), 
              safe_float(data.get('price', 0)), data.get('category'), 
              data.get('is_available', True), safe_int(data.get('prep_time', 15)), 
              data.get('image_url')))
        
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Menu item added successfully'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()

@app.route('/api/update_menu_item/<int:item_id>', methods=['POST'])
@login_required('restaurant')
def update_menu_item(item_id):
    user_id = session['user_id']
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if item belongs to user's restaurant
        cursor.execute("""
            SELECT m.id 
            FROM menu_items m
            JOIN restaurants r ON m.restaurant_id = r.id
            WHERE m.id = %s AND r.user_id = %s
        """, (item_id, user_id))
        
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Menu item not found or unauthorized'})
        
        # Update menu item
        update_fields = []
        update_values = []
        
        if 'name' in data:
            update_fields.append("name = %s")
            update_values.append(data['name'])
        if 'description' in data:
            update_fields.append("description = %s")
            update_values.append(data['description'])
        if 'price' in data:
            update_fields.append("price = %s")
            update_values.append(safe_float(data['price']))
        if 'category' in data:
            update_fields.append("category = %s")
            update_values.append(data['category'])
        if 'is_available' in data:
            update_fields.append("is_available = %s")
            update_values.append(data['is_available'])
        if 'prep_time' in data:
            update_fields.append("prep_time = %s")
            update_values.append(safe_int(data['prep_time']))
        
        if update_fields:
            update_values.append(item_id)
            sql = f"UPDATE menu_items SET {', '.join(update_fields)} WHERE id = %s"
            cursor.execute(sql, tuple(update_values))
        
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Menu item updated successfully'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()

@app.route('/api/toggle_item_status/<int:item_id>', methods=['POST'])
@login_required('restaurant')
def toggle_item_status(item_id):
    user_id = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if item belongs to user's restaurant
        cursor.execute("""
            SELECT m.id, m.is_available
            FROM menu_items m
            JOIN restaurants r ON m.restaurant_id = r.id
            WHERE m.id = %s AND r.user_id = %s
        """, (item_id, user_id))
        
        result = cursor.fetchone()
        if not result:
            return jsonify({'success': False, 'message': 'Menu item not found or unauthorized'})
        
        current_status = result[1]
        new_status = not current_status
        
        # Toggle status
        cursor.execute("""
            UPDATE menu_items 
            SET is_available = %s
            WHERE id = %s
        """, (new_status, item_id))
        
        conn.commit()
        
        return jsonify({'success': True, 'message': f'Item {"made available" if new_status else "marked out of stock"}'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()

# Admin management API
@app.route('/api/admin/toggle_user_status/<int:user_id>', methods=['POST'])
@login_required('admin')
def admin_toggle_user_status(user_id):
    admin_id = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get current status
        cursor.execute("SELECT is_active FROM users WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'success': False, 'message': 'User not found'})
        
        current_status = result[0]
        new_status = not current_status
        
        # Update status
        cursor.execute("""
            UPDATE users 
            SET is_active = %s
            WHERE id = %s
        """, (new_status, user_id))
        
        # Log admin action
        cursor.execute("""
            INSERT INTO admin_actions 
            (admin_id, action_type, target_type, target_id, details, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (admin_id, 'toggle_user_status', 'user', user_id, 
              f'Changed user status to {"active" if new_status else "inactive"}', 
              request.remote_addr))
        
        conn.commit()
        
        action = "activated" if new_status else "deactivated"
        return jsonify({'success': True, 'message': f'User {action} successfully'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()

@app.route('/api/admin/toggle_trust_badge/<int:restaurant_id>', methods=['POST'])
@login_required('admin')
def admin_toggle_trust_badge(restaurant_id):
    admin_id = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get current status
        cursor.execute("SELECT trust_badge FROM restaurants WHERE id = %s", (restaurant_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'success': False, 'message': 'Restaurant not found'})
        
        current_status = result[0]
        new_status = not current_status
        
        # Update trust badge
        cursor.execute("""
            UPDATE restaurants 
            SET trust_badge = %s
            WHERE id = %s
        """, (new_status, restaurant_id))
        
        # Log admin action
        cursor.execute("""
            INSERT INTO admin_actions 
            (admin_id, action_type, target_type, target_id, details, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (admin_id, 'toggle_trust_badge', 'restaurant', restaurant_id, 
              f'Changed trust badge to {"verified" if new_status else "unverified"}', 
              request.remote_addr))
        
        conn.commit()
        
        action = "added" if new_status else "removed"
        return jsonify({'success': True, 'message': f'Trust badge {action} successfully'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()

@app.route('/api/get_order_details/<int:order_id>')
@login_required()
def get_order_details(order_id):
    user_id = session['user_id']
    role = session['role']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Build query based on role
        if role == 'admin':
            cursor.execute("""
                SELECT o.*, u.name as customer_name, r.name as restaurant_name,
                       u.credit_score, u.credit_status
                FROM orders o
                JOIN users u ON o.user_id = u.id
                JOIN restaurants r ON o.restaurant_id = r.id
                WHERE o.id = %s
            """, (order_id,))
        elif role == 'restaurant':
            cursor.execute("""
                SELECT o.*, u.name as customer_name, r.name as restaurant_name,
                       u.credit_score, u.credit_status
                FROM orders o
                JOIN users u ON o.user_id = u.id
                JOIN restaurants r ON o.restaurant_id = r.id
                WHERE o.id = %s AND r.user_id = %s
            """, (order_id, user_id))
        else:  # customer
            cursor.execute("""
                SELECT o.*, u.name as customer_name, r.name as restaurant_name,
                       u.credit_score, u.credit_status
                FROM orders o
                JOIN users u ON o.user_id = u.id
                JOIN restaurants r ON o.restaurant_id = r.id
                WHERE o.id = %s AND o.user_id = %s
            """, (order_id, user_id))
        
        order_tuple = cursor.fetchone()
        
        if not order_tuple:
            return jsonify({'success': False, 'message': 'Order not found or unauthorized'})
        
        order = {
            'id': order_tuple[0],
            'order_number': order_tuple[1],
            'user_id': order_tuple[2],
            'restaurant_id': order_tuple[3],
            'total_amount': safe_float(order_tuple[4]),
            'delivery_fee': safe_float(order_tuple[5]),
            'discount_amount': safe_float(order_tuple[6]),
            'final_amount': safe_float(order_tuple[7]),
            'delivery_address': order_tuple[8],
            'payment_method': order_tuple[9],
            'payment_status': order_tuple[10],
            'status': order_tuple[11],
            'customer_credit_score': safe_int(order_tuple[12]),
            'created_at': order_tuple[20],
            'customer_name': order_tuple[24],
            'restaurant_name': order_tuple[25],
            'credit_score': safe_int(order_tuple[26]),
            'credit_status': order_tuple[27]
        }
        
        # Get order items
        cursor.execute("""
            SELECT oi.*, mi.name
            FROM order_items oi
            JOIN menu_items mi ON oi.menu_item_id = mi.id
            WHERE oi.order_id = %s
        """, (order_id,))
        
        items_tuples = cursor.fetchall()
        items = []
        for item in items_tuples:
            items.append({
                'id': item[0],
                'order_id': item[1],
                'menu_item_id': item[2],
                'quantity': safe_int(item[3]),
                'price': safe_float(item[4]),
                'name': item[6]
            })
        
        return jsonify({'success': True, 'order': order, 'items': items})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()

@app.route('/api/get_order_items/<int:order_id>')
@login_required()
def get_order_items(order_id):
    user_id = session['user_id']
    role = session['role']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check permissions
        if role == 'admin':
            # Admin can see all orders
            pass
        elif role == 'restaurant':
            cursor.execute("""
                SELECT 1 FROM orders o
                JOIN restaurants r ON o.restaurant_id = r.id
                WHERE o.id = %s AND r.user_id = %s
            """, (order_id, user_id))
            if not cursor.fetchone():
                return jsonify({'success': False, 'message': 'Unauthorized'})
        else:  # customer
            cursor.execute("SELECT 1 FROM orders WHERE id = %s AND user_id = %s", (order_id, user_id))
            if not cursor.fetchone():
                return jsonify({'success': False, 'message': 'Unauthorized'})
        
        # Get order items
        cursor.execute("""
            SELECT oi.*, mi.name
            FROM order_items oi
            JOIN menu_items mi ON oi.menu_item_id = mi.id
            WHERE oi.order_id = %s
        """, (order_id,))
        
        items_tuples = cursor.fetchall()
        items = []
        for item in items_tuples:
            items.append({
                'id': item[0],
                'order_id': item[1],
                'menu_item_id': item[2],
                'quantity': safe_int(item[3]),
                'price': safe_float(item[4]),
                'name': item[6]
            })
        
        return jsonify({'success': True, 'items': items})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()

@app.route('/api/toggle_restaurant_status', methods=['POST'])
@login_required('restaurant')
def toggle_restaurant_status():
    user_id = session['user_id']
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get restaurant ID
        cursor.execute("SELECT id, is_open FROM restaurants WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'success': False, 'message': 'Restaurant not found'})
        
        restaurant_id = result[0]
        current_status = result[1]
        
        # Toggle or set specific status
        if 'is_open' in data:
            new_status = data['is_open']
        else:
            new_status = not current_status
        
        # Update status
        cursor.execute("""
            UPDATE restaurants 
            SET is_open = %s
            WHERE id = %s
        """, (new_status, restaurant_id))
        
        conn.commit()
        
        status_text = "opened" if new_status else "closed"
        return jsonify({'success': True, 'message': f'Restaurant {status_text} successfully'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error='Page not found'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', error='Internal server error'), 500


# # Customer browsing routes
# @app.route('/customer/restaurants')
# @login_required('customer')
# def customer_restaurants():
#     """Show all restaurants to customers"""
#     conn = get_db_connection()
#     cursor = conn.cursor()
    
#     # Get all open restaurants
#     cursor.execute("""
#         SELECT r.*, 
#                COUNT(o.id) as total_orders,
#                AVG(TIMESTAMPDIFF(MINUTE, o.created_at, o.actual_delivery_time)) as avg_delivery_time,
#                AVG(o.restaurant_feedback) as avg_rating
#         FROM restaurants r
#         LEFT JOIN orders o ON r.id = o.restaurant_id AND o.status = 'completed'
#         WHERE r.is_open = TRUE
#         GROUP BY r.id
#         ORDER BY r.trust_badge DESC, avg_rating DESC
#     """)
    
#     restaurants_tuples = cursor.fetchall()
#     restaurants = []
#     for rest in restaurants_tuples:
#         restaurants.append({
#             'id': rest[0],
#             'name': rest[2],
#             'description': rest[3],
#             'address': rest[4],
#             'phone': rest[5],
#             'cuisine_type': rest[7],
#             'is_open': bool(rest[10]),
#             'avg_prep_time': safe_int(rest[11]),
#             'rating': safe_float(rest[12]),
#             'trust_badge': bool(rest[14]),
#             'total_orders': safe_int(rest[24]),
#             'avg_delivery_time': safe_float(rest[25]),
#             'avg_rating': safe_float(rest[26])
#         })
    
#     cursor.close()
    
#     return render_template('customer/restaurants.html', restaurants=restaurants)



# @app.route('/customer/restaurants')
# @login_required('customer')
# def customer_restaurants():
#     """Show all restaurants to customers"""
#     conn = get_db_connection()
#     cursor = conn.cursor()
    
#     # Get all open restaurants with simpler query
#     cursor.execute("""
#         SELECT r.id, r.name, r.description, r.address, r.phone, r.cuisine_type,
#                r.is_open, r.avg_prep_time, r.rating, r.trust_badge
#         FROM restaurants r
#         WHERE r.is_open = TRUE
#         ORDER BY r.trust_badge DESC, r.rating DESC
#     """)
    
#     restaurants_tuples = cursor.fetchall()
#     restaurants = []
#     for rest in restaurants_tuples:
#         restaurants.append({
#             'id': rest[0],
#             'name': rest[1],
#             'description': rest[2],
#             'address': rest[3],
#             'phone': rest[4],
#             'cuisine_type': rest[5],
#             'is_open': bool(rest[6]),
#             'avg_prep_time': safe_int(rest[7]),
#             'rating': safe_float(rest[8]),
#             'trust_badge': bool(rest[9])
#         })
    
#     cursor.close()
    
#     return render_template('customer/restaurants.html', restaurants=restaurants)




# @app.route('/customer/restaurants')
# @login_required('customer')
# def customer_restaurants():
#     """Show all restaurants to customers"""
#     conn = get_db_connection()
#     cursor = conn.cursor()
    
#     # Get all open restaurants with simpler query
#     cursor.execute("""
#         SELECT r.id, r.name, r.description, r.address, r.phone, r.cuisine_type,
#                r.is_open, r.avg_prep_time, r.rating, r.trust_badge
#         FROM restaurants r
#         WHERE r.is_open = TRUE
#         ORDER BY r.trust_badge DESC, r.rating DESC
#     """)
    
#     restaurants_tuples = cursor.fetchall()
#     restaurants = []
#     for rest in restaurants_tuples:
#         restaurants.append({
#             'id': rest[0],
#             'name': rest[1],
#             'description': rest[2],
#             'address': rest[3],
#             'phone': rest[4],
#             'cuisine_type': rest[5],
#             'is_open': bool(rest[6]),
#             'avg_prep_time': safe_int(rest[7]),
#             'rating': safe_float(rest[8]),
#             'trust_badge': bool(rest[9])
#         })
    
#     cursor.close()
    
#     # Calculate discount based on credit score
#     credit_score = session.get('credit_score', 70)
#     discount = 0
    
#     if credit_score >= 90:
#         discount = 20
#     elif credit_score >= 75:
#         discount = 15
#     elif credit_score >= 50:
#         discount = 10
#     elif credit_score >= 30:
#         discount = 5
    
#     return render_template('customer/restaurants.html', 
#                          restaurants=restaurants,
#                          discount=discount)


@app.route('/customer/restaurants')
@login_required('customer')
def customer_restaurants():
    """Show all restaurants to customers"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all open restaurants with simpler query
    cursor.execute("""
        SELECT r.id, r.name, r.description, r.address, r.phone, r.cuisine_type,
               r.is_open, r.avg_prep_time, r.rating, r.trust_badge
        FROM restaurants r
        WHERE r.is_open = TRUE
        ORDER BY r.trust_badge DESC, r.rating DESC
    """)
    
    restaurants_tuples = cursor.fetchall()
    restaurants = []
    for rest in restaurants_tuples:
        restaurants.append({
            'id': rest[0],
            'name': rest[1],
            'description': rest[2],
            'address': rest[3],
            'phone': rest[4],
            'cuisine_type': rest[5],
            'is_open': bool(rest[6]),
            'avg_prep_time': safe_int(rest[7]),
            'rating': safe_float(rest[8]),
            'trust_badge': bool(rest[9])
        })
    
    cursor.close()
    
    # Calculate discount based on credit score
    credit_score = session.get('credit_score', 70)
    discount = 0
    
    if credit_score >= 90:
        discount = 20
    elif credit_score >= 75:
        discount = 15
    elif credit_score >= 50:
        discount = 10
    elif credit_score >= 30:
        discount = 5
    
    return render_template('customer/restaurants.html', 
                         restaurants=restaurants,
                         discount=discount)

# @app.route('/customer/restaurant/<int:restaurant_id>')
# @login_required('customer')
# def view_restaurant(restaurant_id):
#     """View restaurant details and menu"""
#     conn = get_db_connection()
#     cursor = conn.cursor()
    
#     # Get restaurant details
#     cursor.execute("SELECT * FROM restaurants WHERE id = %s AND is_open = TRUE", (restaurant_id,))
#     restaurant_tuple = cursor.fetchone()
    
#     if not restaurant_tuple:
#         flash('Restaurant not found or closed', 'error')
#         return redirect(url_for('customer_restaurants'))
    
#     restaurant = {
#         'id': restaurant_tuple[0],
#         'name': restaurant_tuple[2],
#         'description': restaurant_tuple[3],
#         'address': restaurant_tuple[4],
#         'phone': restaurant_tuple[5],
#         'email': restaurant_tuple[6],
#         'cuisine_type': restaurant_tuple[7],
#         'is_open': bool(restaurant_tuple[10]),
#         'avg_prep_time': safe_int(restaurant_tuple[11]),
#         'rating': safe_float(restaurant_tuple[12]),
#         'trust_badge': bool(restaurant_tuple[14])
#     }
    
#     # Get menu items
#     cursor.execute("""
#         SELECT * FROM menu_items 
#         WHERE restaurant_id = %s AND is_available = TRUE
#         ORDER BY category, name
#     """, (restaurant_id,))
    
#     menu_items_tuples = cursor.fetchall()
#     menu_items = []
#     for item in menu_items_tuples:
#         menu_items.append({
#             'id': item[0],
#             'name': item[2],
#             'description': item[3],
#             'price': safe_float(item[4]),
#             'category': item[5],
#             'image_url': item[7],
#             'prep_time': safe_int(item[8])
#         })
    
#     # Group menu items by category
#     menu_by_category = {}
#     for item in menu_items:
#         category = item['category'] or 'Uncategorized'
#         if category not in menu_by_category:
#             menu_by_category[category] = []
#         menu_by_category[category].append(item)
    
#     cursor.close()
    
#     return render_template('customer/restaurant_view.html', 
#                          restaurant=restaurant, 
#                          menu_by_category=menu_by_category)




@app.route('/customer/restaurant/<int:restaurant_id>')
@login_required('customer')
def view_restaurant(restaurant_id):
    """View restaurant details and menu"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get restaurant details
    cursor.execute("""
        SELECT id, name, description, address, phone, email, 
               cuisine_type, is_open, avg_prep_time, rating, trust_badge
        FROM restaurants 
        WHERE id = %s AND is_open = TRUE
    """, (restaurant_id,))
    
    restaurant_tuple = cursor.fetchone()
    
    if not restaurant_tuple:
        flash('Restaurant not found or closed', 'error')
        return redirect(url_for('customer_restaurants'))
    
    restaurant = {
        'id': restaurant_tuple[0],
        'name': restaurant_tuple[1],
        'description': restaurant_tuple[2],
        'address': restaurant_tuple[3],
        'phone': restaurant_tuple[4],
        'email': restaurant_tuple[5],
        'cuisine_type': restaurant_tuple[6],
        'is_open': bool(restaurant_tuple[7]),
        'avg_prep_time': safe_int(restaurant_tuple[8]),
        'rating': safe_float(restaurant_tuple[9]),
        'trust_badge': bool(restaurant_tuple[10])
    }
    
    # Get menu items
    cursor.execute("""
        SELECT id, name, description, price, category, image_url, prep_time
        FROM menu_items 
        WHERE restaurant_id = %s AND is_available = TRUE
        ORDER BY category, name
    """, (restaurant_id,))
    
    menu_items_tuples = cursor.fetchall()
    menu_items = []
    for item in menu_items_tuples:
        menu_items.append({
            'id': item[0],
            'name': item[1],
            'description': item[2],
            'price': safe_float(item[3]),
            'category': item[4] or 'Uncategorized',
            'image_url': item[5],
            'prep_time': safe_int(item[6])
        })
    
    # Group menu items by category
    menu_by_category = {}
    for item in menu_items:
        category = item['category']
        if category not in menu_by_category:
            menu_by_category[category] = []
        menu_by_category[category].append(item)
    
    cursor.close()
    
    # Calculate discount based on credit score
    credit_score = session.get('credit_score', 70)
    discount = 0
    
    if credit_score >= 90:
        discount = 20
    elif credit_score >= 75:
        discount = 15
    elif credit_score >= 50:
        discount = 10
    elif credit_score >= 30:
        discount = 5
    
    return render_template('customer/restaurant_view.html', 
                         restaurant=restaurant, 
                         menu_by_category=menu_by_category,
                         discount=discount)




# @app.route('/customer/checkout', methods=['POST'])
# @login_required('customer')
# def checkout():
#     """Handle order checkout"""
#     if request.method == 'POST':
#         restaurant_id = request.form.get('restaurant_id')
#         delivery_address = request.form.get('delivery_address')
#         payment_method = request.form.get('payment_method', 'wallet')
        
#         # Get cart items from session
#         cart = session.get('cart', {}).get(str(restaurant_id), {})
        
#         if not cart:
#             flash('Your cart is empty', 'error')
#             return redirect(url_for('view_restaurant', restaurant_id=restaurant_id))
        
#         conn = get_db_connection()
#         cursor = conn.cursor()
        
#         try:
#             # Calculate totals
#             total_amount = 0
#             for item_id, quantity in cart.items():
#                 cursor.execute("SELECT price FROM menu_items WHERE id = %s", (item_id,))
#                 item = cursor.fetchone()
#                 if item:
#                     total_amount += safe_float(item[0]) * quantity
            
#             # Get user's credit score and calculate discount
#             user_id = session['user_id']
#             cursor.execute("SELECT credit_score FROM users WHERE id = %s", (user_id,))
#             credit_result = cursor.fetchone()
#             credit_score = safe_int(credit_result[0] if credit_result else 70)
            
#             discount_percentage = 0
#             if credit_score >= 90:
#                 discount_percentage = 20
#             elif credit_score >= 75:
#                 discount_percentage = 15
#             elif credit_score >= 50:
#                 discount_percentage = 10
#             elif credit_score >= 30:
#                 discount_percentage = 5
            
#             delivery_fee = 30  # Fixed delivery fee
#             discount_amount = total_amount * discount_percentage / 100
#             final_amount = total_amount + delivery_fee - discount_amount
            
#             # Generate order number
#             order_number = generate_order_id()
            
#             # Create order
#             cursor.execute("""
#                 INSERT INTO orders 
#                 (order_number, user_id, restaurant_id, total_amount, delivery_fee, 
#                  discount_amount, final_amount, delivery_address, payment_method, 
#                  payment_status, customer_credit_score, status)
#                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
#             """, (order_number, user_id, restaurant_id, total_amount, delivery_fee,
#                   discount_amount, final_amount, delivery_address, payment_method,
#                   'completed', credit_score, 'pending'))
            
#             order_id = cursor.lastrowid
            
#             # Add order items
#             for item_id, quantity in cart.items():
#                 cursor.execute("SELECT price FROM menu_items WHERE id = %s", (item_id,))
#                 item = cursor.fetchone()
#                 if item:
#                     price = safe_float(item[0])
#                     cursor.execute("""
#                         INSERT INTO order_items (order_id, menu_item_id, quantity, price)
#                         VALUES (%s, %s, %s, %s)
#                     """, (order_id, item_id, quantity, price))
            
#             # Add notification for restaurant
#             cursor.execute("SELECT user_id FROM restaurants WHERE id = %s", (restaurant_id,))
#             restaurant_user = cursor.fetchone()
            
#             if restaurant_user:
#                 cursor.execute("""
#                     INSERT INTO notifications (user_id, title, message, type)
#                     VALUES (%s, 'New Order', %s, 'info')
#                 """, (restaurant_user[0], f'You have a new order #{order_number}'))
            
#             # Clear cart
#             if 'cart' in session:
#                 if str(restaurant_id) in session['cart']:
#                     del session['cart'][str(restaurant_id)]
            
#             conn.commit()
            
#             flash(f'Order #{order_number} placed successfully!', 'success')
#             return redirect(url_for('customer_orders'))
            
#         except Exception as e:
#             conn.rollback()
#             flash(f'Error placing order: {str(e)}', 'error')
#             return redirect(url_for('view_restaurant', restaurant_id=restaurant_id))
#         finally:
#             cursor.close()
    
#     return redirect(url_for('customer_restaurants'))





@app.route('/customer/checkout', methods=['POST'])
@login_required('customer')
def checkout():
    """Handle order checkout"""
    if request.method == 'POST':
        restaurant_id = request.form.get('restaurant_id')
        delivery_address = request.form.get('delivery_address')
        payment_method = request.form.get('payment_method', 'cod')
        
        # Get cart items from session
        cart = session.get('cart', {}).get(str(restaurant_id), {})
        
        if not cart:
            flash('Your cart is empty', 'error')
            return redirect(url_for('view_restaurant', restaurant_id=restaurant_id))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Calculate totals
            total_amount = 0
            items_details = []
            
            for item_id, quantity in cart.items():
                cursor.execute("SELECT id, name, price FROM menu_items WHERE id = %s AND is_available = TRUE", (item_id,))
                item = cursor.fetchone()
                if item:
                    price = safe_float(item[2])
                    item_total = price * quantity
                    total_amount += item_total
                    items_details.append({
                        'id': item[0],
                        'name': item[1],
                        'price': price,
                        'quantity': quantity,
                        'item_total': item_total
                    })
            
            if total_amount == 0:
                flash('No valid items in cart', 'error')
                return redirect(url_for('view_restaurant', restaurant_id=restaurant_id))
            
            # Get user's credit score and calculate discount
            user_id = session['user_id']
            cursor.execute("SELECT credit_score FROM users WHERE id = %s", (user_id,))
            credit_result = cursor.fetchone()
            credit_score = safe_int(credit_result[0] if credit_result else 70)
            
            discount_percentage = 0
            if credit_score >= 90:
                discount_percentage = 20
            elif credit_score >= 75:
                discount_percentage = 15
            elif credit_score >= 50:
                discount_percentage = 10
            elif credit_score >= 30:
                discount_percentage = 5
            
            delivery_fee = 30 if total_amount < 500 else 0  # Free delivery for orders above 500
            discount_amount = total_amount * discount_percentage / 100
            final_amount = total_amount + delivery_fee - discount_amount
            
            # Generate order number
            order_number = generate_order_id()
            
            # Set payment status based on payment method
            payment_status = 'completed' if payment_method != 'cod' else 'pending'
            
            # Create order
            cursor.execute("""
                INSERT INTO orders 
                (order_number, user_id, restaurant_id, total_amount, delivery_fee, 
                 discount_amount, final_amount, delivery_address, payment_method, 
                 payment_status, customer_credit_score, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (order_number, user_id, restaurant_id, total_amount, delivery_fee,
                  discount_amount, final_amount, delivery_address, payment_method,
                  payment_status, credit_score, 'pending'))
            
            order_id = cursor.lastrowid
            
            # Add order items
            for item in items_details:
                cursor.execute("""
                    INSERT INTO order_items (order_id, menu_item_id, quantity, price)
                    VALUES (%s, %s, %s, %s)
                """, (order_id, item['id'], item['quantity'], item['price']))
            
            # Add notification for restaurant
            cursor.execute("SELECT user_id FROM restaurants WHERE id = %s", (restaurant_id,))
            restaurant_user = cursor.fetchone()
            
            if restaurant_user:
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, type)
                    VALUES (%s, 'New Order', %s, 'info')
                """, (restaurant_user[0], f'You have a new order #{order_number} (Total: ₹{final_amount:.2f})'))
            
            # Add notification for customer
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, type)
                VALUES (%s, 'Order Confirmed', %s, 'success')
            """, (user_id, f'Your order #{order_number} has been placed successfully. Total: ₹{final_amount:.2f}'))
            
            # Clear cart
            if 'cart' in session:
                if str(restaurant_id) in session['cart']:
                    del session['cart'][str(restaurant_id)]
            
            conn.commit()
            
            # Prepare success message based on payment method
            if payment_method == 'cod':
                message = f'Order #{order_number} placed successfully! Pay ₹{final_amount:.2f} on delivery.'
            else:
                message = f'Order #{order_number} placed successfully! Payment completed.'
            
            flash(message, 'success')
            return redirect(url_for('customer_orders'))
            
        except Exception as e:
            conn.rollback()
            print(f"Error in checkout: {e}")
            flash(f'Error placing order: {str(e)}', 'error')
            return redirect(url_for('view_restaurant', restaurant_id=restaurant_id))
        finally:
            cursor.close()
    
    return redirect(url_for('customer_restaurants'))






# Cart management API
@app.route('/api/add_to_cart', methods=['POST'])
@login_required('customer')
def add_to_cart():
    """Add item to cart"""
    data = request.json
    restaurant_id = data.get('restaurant_id')
    item_id = data.get('item_id')
    quantity = safe_int(data.get('quantity', 1))
    
    # Initialize cart in session if not exists
    if 'cart' not in session:
        session['cart'] = {}
    
    if str(restaurant_id) not in session['cart']:
        session['cart'][str(restaurant_id)] = {}
    
    # Add item to cart
    if str(item_id) in session['cart'][str(restaurant_id)]:
        session['cart'][str(restaurant_id)][str(item_id)] += quantity
    else:
        session['cart'][str(restaurant_id)][str(item_id)] = quantity
    
    session.modified = True
    
    return jsonify({
        'success': True, 
        'message': 'Item added to cart',
        'cart_count': sum(session['cart'][str(restaurant_id)].values())
    })

@app.route('/api/update_cart', methods=['POST'])
@login_required('customer')
def update_cart():
    """Update cart item quantity"""
    data = request.json
    restaurant_id = data.get('restaurant_id')
    item_id = data.get('item_id')
    quantity = safe_int(data.get('quantity', 0))
    
    if 'cart' not in session or str(restaurant_id) not in session['cart']:
        return jsonify({'success': False, 'message': 'Cart not found'})
    
    if quantity <= 0:
        # Remove item from cart
        if str(item_id) in session['cart'][str(restaurant_id)]:
            del session['cart'][str(restaurant_id)][str(item_id)]
    else:
        # Update quantity
        session['cart'][str(restaurant_id)][str(item_id)] = quantity
    
    session.modified = True
    
    return jsonify({
        'success': True, 
        'message': 'Cart updated',
        'cart_count': sum(session['cart'][str(restaurant_id)].values()) if str(restaurant_id) in session['cart'] else 0
    })

@app.route('/api/get_cart/<int:restaurant_id>')
@login_required('customer')
def get_cart(restaurant_id):
    """Get cart contents"""
    cart_items = []
    total = 0
    
    if 'cart' in session and str(restaurant_id) in session['cart']:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for item_id, quantity in session['cart'][str(restaurant_id)].items():
            cursor.execute("""
                SELECT id, name, price, image_url 
                FROM menu_items 
                WHERE id = %s AND is_available = TRUE
            """, (item_id,))
            
            item = cursor.fetchone()
            if item:
                price = safe_float(item[2])
                cart_items.append({
                    'id': item[0],
                    'name': item[1],
                    'price': price,
                    'image_url': item[3],
                    'quantity': quantity,
                    'subtotal': price * quantity
                })
                total += price * quantity
        
        cursor.close()
    
    return jsonify({
        'success': True,
        'cart_items': cart_items,
        'total': total,
        'item_count': len(cart_items)
    })

@app.route('/api/clear_cart/<int:restaurant_id>', methods=['POST'])
@login_required('customer')
def clear_cart(restaurant_id):
    """Clear cart for a restaurant"""
    if 'cart' in session and str(restaurant_id) in session['cart']:
        del session['cart'][str(restaurant_id)]
        session.modified = True
    
    return jsonify({'success': True, 'message': 'Cart cleared'})

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True, port=5000)