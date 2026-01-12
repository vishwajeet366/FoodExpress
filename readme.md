🍽️ FoodExpress - University Food Pre-Booking System
A specialized food pre-booking and delivery system designed for Parul University (and similar educational institutions) to manage campus food rush hours, help restaurants with demand forecasting, and provide students with a seamless food ordering experience.

📖 Project Overview
Problem Statement: During peak hours (12:00 PM - 2:00 PM), university cafeterias and campus food shops face massive crowds, leading to:

Long waiting times for students

Inefficient food preparation for shops

Wasted food due to improper demand estimation

Chaotic rush during lunch breaks

Solution: FoodExpress provides a pre-booking system where students can:

Browse campus food shops

Pre-order meals for specific time slots

Get guaranteed delivery/pickup without waiting

Earn discounts through good ordering behavior

Help shops prepare exact quantities in advance

🎯 Target Users
👨‍🎓 Students (Primary Users)
Pre-book meals from campus food shops

Avoid lunchtime queues

Get discounts based on reliability score

Track order status in real-time

🏪 Campus Food Shops/Restaurants
Receive pre-orders with exact quantities

Prepare food in advance based on bookings

Reduce food wastage

Manage inventory efficiently

Rate student customers for reliability

👨‍🏫 University Administration
Monitor campus food services

View analytics and demand patterns

Ensure food quality and hygiene standards

Manage shop licenses and approvals

🚀 Tech Stack
Frontend: HTML5, CSS3, JavaScript, Bootstrap 5

Backend: Flask (Python)

Database: MySQL

Authentication: Session-based with password hashing

Payment: Cash on Delivery (University Context)

Email: Flask-Mail for notifications

📋 Prerequisites
Before you begin, ensure you have:

Python 3.8+ installed

MySQL installed and running

Git installed (for cloning)

Text Editor/IDE (VS Code recommended)

⚡ Quick Start (5-Minute Setup)
Step 1: Clone the Repository
bash

# Open terminal/command prompt and run:

git clone https://github.com/vishwajeet366/FoodExpress.git
cd FoodExpress
Step 2: Create and Activate Virtual Environment
Windows:
bash
python -m venv venv
venv\Scripts\activate
Mac/Linux:
bash
python3 -m venv venv
source venv/bin/activate
You'll see (venv) at the beginning of your command line when activated

Step 3: Install Dependencies
bash
pip install -r requirements.txt
Step 4: Configure Environment File
Create a new file named .env in the project root and add:

env

# Flask Configuration

SECRET_KEY=your-university-secret-key-parul123
DEBUG=True

# MySQL Database Configuration

MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DB=foodexpress_parul
MYSQL_PORT=3306

# University Specific Settings

UNIVERSITY_NAME=Parul University
CAMPUS_LOCATION=Vadodara
TIMEZONE=Asia/Kolkata
DEFAULT_DELIVERY_FEE=20
FREE_DELIVERY_ABOVE=100

# Email Configuration (Optional - for notifications)

MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
Important: Replace your_mysql_password with your actual MySQL root password.

Step 5: Set Up MySQL Database
Option A: Automatic Setup (Recommended)
Start MySQL service:

bash

# Windows: Open XAMPP/WAMP and start MySQL

# Linux: sudo systemctl start mysql

Run the application once - it will create database automatically:

bash
python app.py
Option B: Manual Setup
Open MySQL Command Line:

bash
mysql -u root -p
Run these commands:

sql
CREATE DATABASE foodexpress_parul;
USE foodexpress_parul;
CREATE USER 'parul_food'@'localhost' IDENTIFIED BY 'parul123';
GRANT ALL PRIVILEGES ON foodexpress_parul.\* TO 'parul_food'@'localhost';
FLUSH PRIVILEGES;
EXIT;
Update .env file:

env
MYSQL_USER=parul_food
MYSQL_PASSWORD=parul123
Step 6: Run the Application
bash
python app.py
Step 7: Access the Application
Open your browser and visit:

text
http://localhost:5000
👥 Default Login Credentials

1. Admin Account (University Management)
   Email: admin@paruluniversity.ac.in

Password: admin123

Role: System administrator

2. Restaurant Account (Sample Food Shop)
   Email: cafeteria@parul.ac.in

Password: cafe123

Role: Restaurant owner

3. Student Account (Sample Student)
   Email: student@paruluniversity.ac.in

Password: student123

Role: Customer

Note: You can also register new accounts directly from the website.

📱 How to Use FoodExpress
For Students:
Register/Login

Use your university email (ends with @paruluniversity.ac.in)

Fill basic details (name, phone, hostel/block number)

Browse Campus Food Shops

View all open food shops in campus

Filter by cuisine type (North Indian, Chinese, Fast Food, etc.)

See shop ratings and preparation time

Pre-book Your Meal

Select time slot (11:00 AM, 12:00 PM, 1:00 PM, etc.)

Add items to cart

Choose delivery location (Hostel, Library, Academic Block, etc.)

Pay via Cash on Delivery (University context)

Track Your Order

Real-time status updates

Estimated delivery time

Notification when food is ready

For Food Shop Owners:
Register Your Shop

Provide shop details

Upload menu with prices

Set preparation time for each item

Define operating hours

Manage Pre-orders

View upcoming orders for each time slot

Accept/Reject orders based on capacity

Update order status (Preparing → Ready → Delivered)

Rate Students

Rate students on punctuality (did they collect on time?)

Rate on politeness

This affects student's credit score

For University Admin:
Monitor Campus Food Services

View all registered food shops

Monitor hygiene ratings

Handle complaints

Analytics Dashboard

Peak ordering hours

Most popular food items

Shop performance metrics

Manage Student Accounts

View student ordering patterns

Adjust credit scores if needed

Resolve disputes

🏗️ Project Structure
text
FoodExpress/
├── app.py # Main Flask application
├── .env # Environment variables (YOU CREATE THIS)
├── config.py # Configuration settings
├── requirements.txt # Python dependencies
├── README.md # This file
├── templates/ # HTML Templates
│ ├── auth/ # Login/Register pages
│ ├── customer/ # Student interface
│ ├── restaurant/ # Food shop interface
│ ├── admin/ # University admin interface
│ └── index.html # Home page
├── static/ # CSS, JS, Images
│ ├── css/
│ │ └── style.css # Custom styles
│ ├── js/
│ │ └── main.js # JavaScript functions
│ └── images/ # Logos and food images
└── database_backup/ # Sample data (if any)
🔧 Key Features for University Context

1. Time Slot Based Booking
   Students can book for specific lunch/dinner slots

Shops know exact demand for each time period

Avoids last-minute rush

2. Campus Delivery Zones
   Pre-defined delivery locations

Hostels, Library, Academic Blocks, Sports Complex

Optimized delivery routes

3. Student Credit System
   Starts with 70 points for all students

Increases with on-time payments and pickups

Decreases with cancellations or no-shows

Higher credit = Better discounts

4. Shop Trust Badge
   Verified by university administration

Maintains hygiene standards

Timely order fulfillment

Displayed to students for trust

5. University Admin Controls
   Approve new food shops

Monitor food prices

Handle student complaints

View campus-wide analytics

📊 Database Schema Overview
users - Students, Shop Owners, Admin

restaurants - Campus food shops

menu_items - Food items with prices

orders - Student bookings with time slots

order_items - Items in each order

credit_history - Student behavior tracking

customer_feedback - Shop ratings for students

notifications - Order updates and alerts

🚀 Deployment Options
For University Lab/Server:
Option 1: Local Network Deployment
bash

# Run on specific IP for lab access

python app.py --host=0.0.0.0 --port=5000
Then access via: http://lab-server-ip:5000

Option 2: Windows Service (For Lab PCs)
Create run_foodexpress.bat:

batch
@echo off
cd C:\FoodExpress
venv\Scripts\activate
python app.py
Add to startup for lab PCs

For Production (University Server):
bash

# Install gunicorn for production

pip install gunicorn

# Run with gunicorn

gunicorn -w 4 -b 0.0.0.0:8000 app:app

# Set up Nginx reverse proxy

# Configure firewall rules

🐛 Troubleshooting Guide
Common Issues:
MySQL Connection Error

text
Solution: Ensure MySQL service is running
Windows: Check XAMPP/WAMP control panel
Linux: sudo systemctl status mysql
Port 5000 Already in Use

text
Solution: Change port in app.py
app.run(debug=True, port=5001)
Module Not Found

text
Solution: Ensure virtual environment is activated
Check: (venv) should appear in terminal
Database Tables Not Created

text
Solution: Check MySQL credentials in .env
Ensure database exists: foodexpress_parul
Email Not Working

text
Solution: For Gmail, enable "App Passwords"
Or comment out email features in config.py
Quick Fix Commands:
bash

# Reset everything and start fresh

cd FoodExpress
deactivate # Exit any existing venv
rm -rf venv # Linux/Mac
rmdir /s venv # Windows

# Recreate from scratch

python -m venv venv
venv\Scripts\activate # Windows
source venv/bin/activate # Mac/Linux
pip install -r requirements.txt
python app.py
📝 Project Customization for Your University

1. Change University Name
   Edit .env file:

env
UNIVERSITY_NAME=Your University Name 2. Add Campus Locations
Modify in app.py - search for delivery locations and update.

3. Customize Time Slots
   Modify booking time slots in customer templates.

4. Add Your Logo
   Replace static/images/logo.png with your university logo.

5. Set Academic Year
   Update default settings in config.py.

🎓 For College Projects/Submissions
What to Demonstrate:
Student Registration & Login

Browse Food Shops

Add Items to Cart

Pre-book for Time Slot

Track Order Status

Restaurant Dashboard

Admin Analytics

Project Report Points:
Problem Statement (Campus Food Rush)

Solution (Pre-booking System)

Tech Stack Used

Database Design

Screenshots of working system

Future Enhancements

📞 Support & Contact
Developer: Vishwajeet
GitHub: https://github.com/vishwajeet366
Project: FoodExpress
For: Parul University Minor Project

For Issues:

Check troubleshooting section

Review error messages in terminal

Ensure all prerequisites are met

Contact with screenshot of error

🔮 Future Enhancements (For Major Project)
Mobile App - React Native for iOS/Android

QR Code Pickup - Scan and collect orders

Meal Plans - Weekly/Monthly subscription

Diet Tracking - Calories and nutrition info

Payment Integration - UPI, Card payments

Delivery Tracking - Real-time GPS tracking

AI Predictions - Demand forecasting

Feedback System - Rate food quality

📄 License
This project is developed for educational purposes at Parul University. Feel free to modify and use for your college projects.
