from flask import Flask, url_for, render_template, request, redirect, session, jsonify, send_from_directory, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import random
import os
import json
from werkzeug.security import generate_password_hash, check_password_hash
import joblib
from sklearn.ensemble import RandomForestRegressor
import matplotlib
matplotlib.use('Agg')  # Set the backend before importing pyplot
import matplotlib.pyplot as plt
from route_model import RouteOptimizer
import traceback
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from sqlalchemy import func
import math
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import folium
from folium import plugins

app = Flask(__name__, static_url_path='', static_folder='static')
app.secret_key = 'your_secret_key_here'  # Required for session management

# Ensure the route_maps directory exists
os.makedirs(os.path.join(app.root_path, 'static', 'route_maps'), exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Suppress warnings

db = SQLAlchemy(app)

# Database model for users
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(170), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    city = db.Column(db.String(80), nullable=True)

# Vehicle model
class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_name = db.Column(db.String(100), nullable=False)
    vehicle_number = db.Column(db.String(50), unique=True, nullable=False)
    owner_name = db.Column(db.String(100), nullable=False)
    battery_status = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    speed = db.Column(db.Float, nullable=False)

# Driver Behavior model
class DriverBehavior(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    speed = db.Column(db.Float, nullable=False)
    harsh_braking = db.Column(db.Boolean, default=False)
    rapid_acceleration = db.Column(db.Boolean, default=False)
    idle_time = db.Column(db.Integer, default=0)  # in minutes
    score = db.Column(db.Integer, nullable=False)

# Maintenance Alert model
class MaintenanceAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)
    alert_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    priority = db.Column(db.String(20), nullable=False)  # High, Medium, Low
    status = db.Column(db.String(20), nullable=False)  # Open, Closed

# Report model
class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_type = db.Column(db.String(100), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    generated_at = db.Column(db.DateTime, nullable=False)

# ConsumptionMetric model
class ConsumptionMetric(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    energy_used = db.Column(db.Float, nullable=False)  # in kWh
    cost = db.Column(db.Float, nullable=False)  # in INR
    distance = db.Column(db.Float, nullable=False)  # in km
    efficiency = db.Column(db.Float)  # kWh/km
    vehicle = db.relationship('Vehicle', backref='consumption_metrics')

# Initialize the geocoder
geolocator = Nominatim(user_agent="ev_fleet_monitoring")

def get_coordinates(address):
    """Get coordinates (latitude, longitude) for a given address"""
    try:
        # Add 'India' to the address if not present to improve geocoding accuracy
        if 'india' not in address.lower():
            address += ', India'
            
        location = geolocator.geocode(address)
        if location:
            return (location.latitude, location.longitude)
        return None
    except GeocoderTimedOut:
        return None
    except Exception as e:
        print(f"Error in geocoding: {str(e)}")
        return None

# Vehicle API routes
@app.route('/api/vehicle/<int:id>', methods=['GET'])
def get_vehicle(id):
    if not session.get('logged_in'):
        return jsonify({'error': 'Not logged in'}), 401
    vehicle = Vehicle.query.get_or_404(id)
    return jsonify({
        'id': vehicle.id,
        'vehicle_name': vehicle.vehicle_name,
        'vehicle_number': vehicle.vehicle_number,
        'owner_name': vehicle.owner_name,
        'location': vehicle.location,
        'battery_status': vehicle.battery_status,
        'speed': vehicle.speed
    })

@app.route('/api/vehicle/<int:id>', methods=['PUT'])
def update_vehicle(id):
    if not session.get('logged_in'):
        return jsonify({'error': 'Not logged in'}), 401
    vehicle = Vehicle.query.get_or_404(id)
    data = request.get_json()
    
    vehicle.vehicle_name = data.get('vehicle_name', vehicle.vehicle_name)
    vehicle.vehicle_number = data.get('vehicle_number', vehicle.vehicle_number)
    vehicle.owner_name = data.get('owner_name', vehicle.owner_name)
    vehicle.location = data.get('location', vehicle.location)
    
    db.session.commit()
    return jsonify({'message': 'Vehicle updated successfully'})

@app.route('/api/vehicle/<int:id>', methods=['DELETE'])
def delete_vehicle(id):
    if not session.get('logged_in'):
        return jsonify({'error': 'Not logged in'}), 401
    vehicle = Vehicle.query.get_or_404(id)
    db.session.delete(vehicle)
    db.session.commit()
    return jsonify({'message': 'Vehicle deleted successfully'})

# Function to generate maintenance alerts based on vehicle conditions
def generate_maintenance_alerts():
    vehicles = Vehicle.query.all()
    current_time = datetime.now()
    
    for vehicle in vehicles:
        # Check battery status
        if vehicle.battery_status < 20:
            alert = MaintenanceAlert.query.filter_by(
                vehicle_id=vehicle.id,
                alert_type='Low Battery',
                status='Open'
            ).first()
            
            if not alert:
                new_alert = MaintenanceAlert(
                    vehicle_id=vehicle.id,
                    alert_type='Low Battery',
                    description=f'Battery level critically low ({vehicle.battery_status}%). Immediate charging required.',
                    timestamp=current_time,
                    priority='High',
                    status='Open'
                )
                db.session.add(new_alert)
        
        # Simulate temperature monitoring (random temperature between 20-80°C)
        temperature = random.uniform(20, 80)
        if temperature > 60:
            alert = MaintenanceAlert.query.filter_by(
                vehicle_id=vehicle.id,
                alert_type='High Temperature',
                status='Open'
            ).first()
            
            if not alert:
                new_alert = MaintenanceAlert(
                    vehicle_id=vehicle.id,
                    alert_type='High Temperature',
                    description=f'Battery temperature too high ({temperature:.1f}°C). Immediate inspection required.',
                    timestamp=current_time,
                    priority='High',
                    status='Open'
                )
                db.session.add(new_alert)
        
        # Generate maintenance schedule alerts
        last_maintenance = random.randint(80, 200)  # Simulated days since last maintenance
        if last_maintenance > 180:  # If last maintenance was more than 6 months ago
            alert = MaintenanceAlert.query.filter_by(
                vehicle_id=vehicle.id,
                alert_type='Scheduled Maintenance',
                status='Open'
            ).first()
            
            if not alert:
                new_alert = MaintenanceAlert(
                    vehicle_id=vehicle.id,
                    alert_type='Scheduled Maintenance',
                    description=f'Vehicle due for scheduled maintenance. Last service: {last_maintenance} days ago.',
                    timestamp=current_time,
                    priority='Medium',
                    status='Open'
                )
                db.session.add(new_alert)
    
    db.session.commit()

# Function to generate driver behavior data
def generate_driver_behavior():
    vehicles = Vehicle.query.all()
    current_time = datetime.now()
    
    for vehicle in vehicles:
        # Generate random behavior metrics
        speed = vehicle.speed
        harsh_braking = speed > 60 and random.random() < 0.3
        rapid_acceleration = speed > 40 and random.random() < 0.25
        idle_time = random.randint(0, 30)
        
        # Calculate driver score based on behavior
        base_score = 100
        if harsh_braking:
            base_score -= 15
        if rapid_acceleration:
            base_score -= 10
        if idle_time > 15:
            base_score -= 5
        if speed > 70:
            base_score -= 20
        
        final_score = max(min(base_score, 100), 0)
        
        # Record driver behavior
        behavior = DriverBehavior(
            vehicle_id=vehicle.id,
            timestamp=current_time,
            speed=speed,
            harsh_braking=harsh_braking,
            rapid_acceleration=rapid_acceleration,
            idle_time=idle_time,
            score=final_score
        )
        db.session.add(behavior)
    
    db.session.commit()

# Home route
@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    try:
        # Ensure we have some sample data
        ensure_sample_data()
        
        # Get all vehicles
        vehicles = Vehicle.query.all()
        total_vehicles = len(vehicles)
        
        # Initialize default values
        context = {
            'total_vehicles': 0,
            'avg_battery': 0,
            'charging_vehicles': 0,
            'active_vehicles': 0,
            'status_labels': [],
            'status_data': [],
            'battery_labels': [],
            'battery_data': [],
            'vehicles': [],
            'recent_activities': []
        }
        
        if total_vehicles > 0:
            # Calculate statistics
            battery_levels = [v.battery_status for v in vehicles]
            avg_battery = round(sum(battery_levels) / total_vehicles)
            
            # Count vehicles by status
            charging_vehicles = sum(1 for v in vehicles if v.battery_status < 20)
            active_vehicles = sum(1 for v in vehicles if v.speed > 0)
            
            # Prepare vehicle status data for pie chart
            status_categories = {
                'Active': sum(1 for v in vehicles if v.speed > 0),
                'Charging': sum(1 for v in vehicles if v.battery_status < 20),
                'Inactive': sum(1 for v in vehicles if v.speed == 0 and v.battery_status >= 20),
                'Maintenance': sum(1 for v in vehicles if v.battery_status < 10)
            }
            
            # Prepare vehicle list with status classes
            vehicle_list = []
            for vehicle in vehicles:
                status = 'Active' if vehicle.speed > 0 else 'Charging' if vehicle.battery_status < 20 else 'Inactive'
                status_class = f'status-{status.lower()}'
                vehicle_list.append({
                    'vehicle_name': vehicle.vehicle_name,
                    'battery_status': vehicle.battery_status,
                    'status': status,
                    'status_class': status_class,
                    'location': vehicle.location
                })
            
            # Generate real recent activities with debugging
            print("Generating recent activities...")
            recent_activities = generate_recent_activities()
            print(f"Generated activities: {recent_activities}")
            
            # Update context with actual data
            context.update({
                'total_vehicles': total_vehicles,
                'avg_battery': avg_battery,
                'charging_vehicles': charging_vehicles,
                'active_vehicles': active_vehicles,
                'status_labels': list(status_categories.keys()),
                'status_data': list(status_categories.values()),
                'battery_labels': ['0-20%', '21-40%', '41-60%', '61-80%', '81-100%'],
                'battery_data': [
                    sum(1 for v in vehicles if 0 <= v.battery_status <= 20),
                    sum(1 for v in vehicles if 21 <= v.battery_status <= 40),
                    sum(1 for v in vehicles if 41 <= v.battery_status <= 60),
                    sum(1 for v in vehicles if 61 <= v.battery_status <= 80),
                    sum(1 for v in vehicles if 81 <= v.battery_status <= 100)
                ],
                'vehicles': vehicle_list,
                'recent_activities': recent_activities
            })
            print(f"Context recent_activities: {context['recent_activities']}")
        
        return render_template('home.html', **context)
        
    except Exception as e:
        print(f"Error in index route: {str(e)}")
        import traceback
        traceback.print_exc()
        return render_template('home.html', error=str(e), **{
            'total_vehicles': 0,
            'avg_battery': 0,
            'charging_vehicles': 0,
            'active_vehicles': 0,
            'status_labels': [],
            'status_data': [],
            'battery_labels': [],
            'battery_data': [],
            'vehicles': [],
            'recent_activities': []
        })

def ensure_sample_data():
    """
    Ensure there's some sample data in the database for testing
    """
    # Check if we have any vehicles
    if Vehicle.query.count() == 0:
        print("No vehicles found. Creating sample vehicles.")
        # Create sample vehicles
        sample_vehicles = [
            Vehicle(vehicle_name='EV-1', vehicle_number='KA01AB1234', 
                    owner_name='John Doe', battery_status=75, 
                    location='Bangalore', speed=0),
            Vehicle(vehicle_name='EV-2', vehicle_number='KA01CD5678', 
                    owner_name='Jane Smith', battery_status=45, 
                    location='Mysore', speed=30)
        ]
        db.session.add_all(sample_vehicles)
        db.session.commit()
    
    # Check if we have any maintenance alerts
    if MaintenanceAlert.query.count() == 0:
        print("No maintenance alerts found. Creating sample alerts.")
        vehicles = Vehicle.query.all()
        if vehicles:
            sample_alerts = [
                MaintenanceAlert(
                    vehicle_id=vehicles[0].id,
                    alert_type='Battery',
                    description='Low battery level detected',
                    timestamp=datetime.now(),
                    priority='High',
                    status='Open'
                ),
                MaintenanceAlert(
                    vehicle_id=vehicles[1].id,
                    alert_type='Tire Pressure',
                    description='Low tire pressure warning',
                    timestamp=datetime.now(),
                    priority='Medium',
                    status='Open'
                )
            ]
            db.session.add_all(sample_alerts)
            db.session.commit()
    
    # Check if we have any driver behavior records
    if DriverBehavior.query.count() == 0:
        print("No driver behavior records found. Creating sample records.")
        vehicles = Vehicle.query.all()
        if vehicles:
            sample_behaviors = [
                DriverBehavior(
                    vehicle_id=vehicles[0].id,
                    timestamp=datetime.now(),
                    speed=50,
                    harsh_braking=True,
                    rapid_acceleration=False,
                    idle_time=20,
                    score=80
                ),
                DriverBehavior(
                    vehicle_id=vehicles[1].id,
                    timestamp=datetime.now(),
                    speed=30,
                    harsh_braking=False,
                    rapid_acceleration=True,
                    idle_time=10,
                    score=70
                )
            ]
            db.session.add_all(sample_behaviors)
            db.session.commit()
    
    # Check if we have any consumption metrics
    if ConsumptionMetric.query.count() == 0:
        print("No consumption metrics found. Creating sample metrics.")
        vehicles = Vehicle.query.all()
        if vehicles:
            sample_metrics = [
                ConsumptionMetric(
                    vehicle_id=vehicles[0].id,
                    timestamp=datetime.now(),
                    energy_used=10.5,
                    cost=315,
                    distance=50,
                    efficiency=1.7
                ),
                ConsumptionMetric(
                    vehicle_id=vehicles[1].id,
                    timestamp=datetime.now(),
                    energy_used=8.2,
                    cost=246,
                    distance=40,
                    efficiency=1.2
                )
            ]
            db.session.add_all(sample_metrics)
            db.session.commit()

def generate_recent_activities():
    """
    Generate recent activities based on actual database records
    Prioritizes recent maintenance alerts, driver behavior events, and consumption metrics
    """
    # Combine activities from different sources
    activities = []
    
    print("Starting to generate recent activities...")
    
    try:
        # Recent Maintenance Alerts
        maintenance_alerts = MaintenanceAlert.query.order_by(MaintenanceAlert.timestamp.desc()).limit(3).all()
        print(f"Found {len(maintenance_alerts)} maintenance alerts")
        for alert in maintenance_alerts:
            vehicle = Vehicle.query.get(alert.vehicle_id)
            if vehicle:
                print(f"Processing alert for vehicle {vehicle.vehicle_name}")
                activities.append({
                    'icon': '🚨',
                    'vehicle_name': vehicle.vehicle_name,
                    'status': f"{alert.alert_type} Alert: {alert.description}",
                    'timestamp': time_ago(alert.timestamp),
                    'priority': alert.priority
                })
        
        # Recent Driver Behavior Events
        driver_behaviors = DriverBehavior.query.order_by(DriverBehavior.timestamp.desc()).limit(3).all()
        print(f"Found {len(driver_behaviors)} driver behaviors")
        for behavior in driver_behaviors:
            vehicle = Vehicle.query.get(behavior.vehicle_id)
            if vehicle:
                status = []
                if behavior.harsh_braking:
                    status.append("Harsh Braking")
                if behavior.rapid_acceleration:
                    status.append("Rapid Acceleration")
                if behavior.idle_time > 15:
                    status.append(f"Long Idle Time: {behavior.idle_time} mins")
                
                if status:
                    print(f"Processing behavior for vehicle {vehicle.vehicle_name}")
                    activities.append({
                        'icon': '🚗',
                        'vehicle_name': vehicle.vehicle_name,
                        'status': ", ".join(status),
                        'timestamp': time_ago(behavior.timestamp),
                        'priority': 'Medium'
                    })
        
        # Recent Consumption Metrics with Unusual Patterns
        consumption_metrics = ConsumptionMetric.query.order_by(ConsumptionMetric.timestamp.desc()).limit(3).all()
        print(f"Found {len(consumption_metrics)} consumption metrics")
        for metric in consumption_metrics:
            vehicle = Vehicle.query.get(metric.vehicle_id)
            if vehicle and metric.efficiency > 1.5:  # High energy consumption
                print(f"Processing consumption metric for vehicle {vehicle.vehicle_name}")
                activities.append({
                    'icon': '⚡',
                    'vehicle_name': vehicle.vehicle_name,
                    'status': f"High Energy Consumption: {metric.efficiency:.2f} kWh/km",
                    'timestamp': time_ago(metric.timestamp),
                    'priority': 'Low'
                })
        
        # If no real activities found, add a default activity
        if not activities:
            print("No activities found, adding default activity")
            activities.append({
                'icon': '🚗',
                'vehicle_name': 'System',
                'status': 'No recent activities',
                'timestamp': 'just now',
                'priority': 'Low'
            })
        
        # Sort activities by timestamp and limit to 5
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        activities = activities[:5]
        
        print(f"Final activities list: {activities}")
        return activities
        
    except Exception as e:
        print(f"Error generating activities: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return a default activity in case of error
        return [{
            'icon': '⚠️',
            'vehicle_name': 'System',
            'status': 'Error loading activities',
            'timestamp': 'just now',
            'priority': 'High'
        }]

def time_ago(timestamp):
    """Convert timestamp to human-readable time ago format"""
    try:
        now = datetime.now()
        diff = now - timestamp
        
        seconds = diff.total_seconds()
        minutes = seconds // 60
        hours = minutes // 60
        days = diff.days
        
        if days > 0:
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif hours > 0:
            return f"{int(hours)} hour{'s' if hours != 1 else ''} ago"
        elif minutes > 0:
            return f"{int(minutes)} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "just now"
    except Exception as e:
        print(f"Error in time_ago: {str(e)}")
        return "recently"

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        uname = request.form["uname"]
        passw = request.form["passw"]

        # Validate user credentials
        login = User.query.filter_by(username=uname, password=passw).first()

        if login:
            session['logged_in'] = True
            session['username'] = uname
            return redirect(url_for('dashboard'))  
        else:
            return render_template("login.html", error="Invalid username or password.")
        
    return render_template("login.html")

# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        uname = request.form['uname']
        email = request.form['email']
        passw = request.form['passw']
        city = request.form['city']

        # Check if the username or email already exists
        if User.query.filter_by(username=uname).first():
            return render_template('registration.html', error="Username already exists!")
        elif User.query.filter_by(email=email).first():
            return render_template('registration.html', error="Email already registered!")

        # Create a new user and add to the database
        new_user = User(username=uname, email=email, password=passw, city=city)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))  # Redirect to login page after successful registration

    return render_template('registration.html')

# register_vehicle route
@app.route('/register_vehicle', methods=['GET', 'POST'])
def register_vehicle():
    if request.method == 'POST':
        vehicle_name = request.form['vehicle_name']
        vehicle_number = request.form['vehicle_number']
        owner_name = request.form['owner_name']
        battery_status = request.form['battery_status']
        location = request.form['location']
        speed = request.form['speed']

        # Check for duplicate vehicle number
        if Vehicle.query.filter_by(vehicle_number=vehicle_number).first():
            return render_template('register_vehicle.html', error="Vehicle number already exists!")
        
        # Add new vehicle to the database
        new_vehicle = Vehicle(
            vehicle_name=vehicle_name,
            vehicle_number=vehicle_number,
            owner_name=owner_name,
            battery_status=battery_status,
            location=location,
            speed=speed
        )
        db.session.add(new_vehicle)
        db.session.commit()
        return redirect(url_for('vehicle_status'))

    return render_template('register_vehicle.html')

# vehicle_status route
@app.route('/vehicle_status')
def vehicle_status():
    vehicles = Vehicle.query.all()
    return render_template('vehicle_status.html', vehicles=vehicles)

# Load the trained model
def load_battery_model():
    model_path = 'battery_health_model.pkl'
    try:
        print(f"Loading model from {model_path}...")
        return joblib.load(model_path)
    except Exception as e:
        print(f"Error loading model: {e}")
        return None

battery_health_model = load_battery_model()

@app.route('/battery_health_status', methods=['GET', 'POST'])
def battery_health_status():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    prediction = None
    health_percentage = None
    error = None

    if request.method == 'POST':
        try:
            if battery_health_model is None:
                raise Exception("Model not loaded properly. Please check if battery_health_model.pkl exists.")

            # Get input values from the form
            capacity = float(request.form['capacity'])
            voltage = float(request.form['voltage'])
            temperature = float(request.form['temperature'])
            
            # Create input data frame with the required features
            # Using 'mOhm' instead of 'mΩ' to avoid encoding issues
            features = ['Capacity (mAh)', 'Voltage (V)', 'Temperature (°C)', 'Internal Resistance (mOhm)']
            values = [[capacity, voltage, temperature, 200]]  # 200 mOhm as default internal resistance
            
            input_data = np.array(values)
            print("Input data for prediction:", input_data)
            
            # Make prediction
            prediction_result = battery_health_model.predict(input_data)
            health_percentage = float(prediction_result[0])
            
            # Determine battery status based on health percentage
            if health_percentage >= 85:
                prediction = "Good"
            elif health_percentage >= 70:
                prediction = "Average"
            else:
                prediction = "Poor"

            print(f"Prediction made - Health: {health_percentage}%, Status: {prediction}")
            
        except Exception as e:
            error = str(e)
            print("Error in battery_health_status:", str(e))

    return render_template('battery_health_status.html', 
                         prediction=prediction,
                         health_percentage=f"{health_percentage:.1f}%" if health_percentage is not None else None,
                         error=error)

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    try:
        # Get all vehicles
        vehicles = Vehicle.query.all()
        total_vehicles = len(vehicles)
        
        if total_vehicles == 0:
            return render_template('index.html',
                total_vehicles=0,
                avg_battery_level=0,
                vehicles_charging=0,
                vehicles_active=0,
                status_data=[],
                battery_distribution=[],
                vehicles=[],
                recent_activities=[]
            )
        
        # Calculate statistics
        battery_levels = [v.battery_status for v in vehicles]
        avg_battery_level = round(sum(battery_levels) / total_vehicles)
        
        # Count vehicles by status
        vehicles_charging = sum(1 for v in vehicles if v.battery_status < 20)
        vehicles_active = sum(1 for v in vehicles if v.speed > 0)
        
        # Prepare vehicle status data for pie chart
        status_data = [
            sum(1 for v in vehicles if v.speed > 0),  # Active
            sum(1 for v in vehicles if v.battery_status < 20),  # Charging
            sum(1 for v in vehicles if v.speed == 0 and v.battery_status >= 20),  # Inactive
            sum(1 for v in vehicles if v.battery_status < 10)  # Maintenance
        ]
        
        # Prepare battery distribution data
        battery_distribution = [
            sum(1 for v in vehicles if 0 <= v.battery_status <= 20),
            sum(1 for v in vehicles if 21 <= v.battery_status <= 40),
            sum(1 for v in vehicles if 41 <= v.battery_status <= 60),
            sum(1 for v in vehicles if 61 <= v.battery_status <= 80),
            sum(1 for v in vehicles if 81 <= v.battery_status <= 100)
        ]
        
        # Prepare vehicle list
        vehicles_data = []
        for vehicle in vehicles:
            status = 'Active' if vehicle.speed > 0 else 'Charging' if vehicle.battery_status < 20 else 'Inactive'
            vehicles_data.append({
                'vehicle_name': vehicle.vehicle_name,
                'battery_status': vehicle.battery_status,
                'status': status,
                'location': vehicle.location
            })
        
        # Generate recent activities
        recent_activities = []
        for i in range(5):
            activity = {
                'vehicle_id': i,
                'message': ['Started charging', 'Completed route', 'Low battery alert', 'Maintenance required'][i % 4],
                'time_ago': f'{i*10} minutes ago'
            }
            recent_activities.append(activity)
        
        return render_template('index.html',
            total_vehicles=total_vehicles,
            avg_battery_level=avg_battery_level,
            vehicles_charging=vehicles_charging,
            vehicles_active=vehicles_active,
            status_data=status_data,
            battery_distribution=battery_distribution,
            vehicles=vehicles_data,
            recent_activities=recent_activities
        )
        
    except Exception as e:
        print(f"Error in dashboard: {str(e)}")
        return render_template('index.html',
            error="Error generating dashboard visualizations",
            total_vehicles=0,
            avg_battery_level=0,
            vehicles_charging=0,
            vehicles_active=0,
            status_data=[],
            battery_distribution=[],
            vehicles=[],
            recent_activities=[]
        )

@app.route('/route_optimization', methods=['GET', 'POST'])
def route_optimization():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('route_optimization.html')

from route_model import RouteOptimizer
route_optimizer = RouteOptimizer()

# Define charging stations along Bangalore-Mysore route
charging_stations = [
    {
        'station_id': 'CS001',
        'name': 'Bidadi Charging Hub',
        'location': {'lat': 12.7969, 'lon': 77.3839},
        'charging_speed': 100,  # kW
        'available_ports': 4
    },
    {
        'station_id': 'CS002',
        'name': 'Ramanagara EV Station',
        'location': {'lat': 12.7248, 'lon': 77.2831},
        'charging_speed': 150,
        'available_ports': 6
    },
    {
        'station_id': 'CS003',
        'name': 'Channapatna Charging Point',
        'location': {'lat': 12.6509, 'lon': 77.2067},
        'charging_speed': 100,
        'available_ports': 3
    },
    {
        'station_id': 'CS004',
        'name': 'Maddur EV Hub',
        'location': {'lat': 12.5858, 'lon': 77.0432},
        'charging_speed': 120,
        'available_ports': 4
    },
    {
        'station_id': 'CS005',
        'name': 'Mandya Charging Station',
        'location': {'lat': 12.5221, 'lon': 76.8951},
        'charging_speed': 150,
        'available_ports': 5
    }
]

@app.route('/optimize_route', methods=['POST'])
def optimize_route():
    try:
        data = request.get_json()
        source = data.get('source', '')
        destination = data.get('destination', '')
        battery_percentage = float(data.get('battery_percentage', 100))

        # Get coordinates for source and destination using RouteOptimizer
        source_coords = route_optimizer.get_coordinates(source)
        if not source_coords[0]:
            return jsonify({'error': 'Invalid source address'})
        
        dest_coords = route_optimizer.get_coordinates(destination)
        if not dest_coords[0]:
            return jsonify({'error': 'Invalid destination address'})

        # Calculate route details using OSRM
        route_details = route_optimizer.get_route_from_osrm(source_coords[:2], dest_coords[:2])
        if not route_details:
            return jsonify({'error': 'Could not calculate route'})

        # Initialize route points with source
        route_points = [{
            'lat': source_coords[0],
            'lon': source_coords[1],
            'name': source
        }]

        # Find charging stations along the route
        total_distance = route_details['distance']
        range_with_current_battery = (battery_percentage / 100) * route_optimizer.AVERAGE_EV_RANGE
        
        if total_distance > range_with_current_battery:
            # Find charging stations near the route
            for station in route_optimizer.find_nearby_stations(source_coords[0], source_coords[1]):
                route_points.append({
                    'lat': station['lat'],
                    'lon': station['lon'],
                    'name': station['name'],
                    'is_charging_station': True,
                    'charging_speed': station['charging_speed'],
                    'available_ports': station['available_ports']
                })

        # Add destination
        route_points.append({
            'lat': dest_coords[0],
            'lon': dest_coords[1],
            'name': destination
        })

        # Create route visualization
        map_file = create_route_map(route_points)
        
        # Get the full URL for the map
        map_url = url_for('static', filename=map_file.replace('static/', ''))
        
        return jsonify({
            'route': map_url,
            'distance': route_details['distance'],
            'duration': route_details['duration'],
            'charging_stations': [point for point in route_points if point.get('is_charging_station', False)],
            'source_address': source_coords[2] or source,
            'dest_address': dest_coords[2] or destination,
            'message': f'Route optimized with {len([p for p in route_points if p.get("is_charging_station", False)])} charging stations'
        })

    except Exception as e:
        print(f"Error in optimize_route: {str(e)}")
        return jsonify({'error': str(e)})

def is_station_on_route(station_loc, source_coords, dest_coords, max_deviation=0.05):
    """Check if a charging station is close enough to the route"""
    station_lat, station_lon = station_loc['lat'], station_loc['lon']
    
    # Simple bounding box check
    min_lat = min(source_coords[0], dest_coords[0]) - max_deviation
    max_lat = max(source_coords[0], dest_coords[0]) + max_deviation
    min_lon = min(source_coords[1], dest_coords[1]) - max_deviation
    max_lon = max(source_coords[1], dest_coords[1]) + max_deviation
    
    return (min_lat <= station_lat <= max_lat and 
            min_lon <= station_lon <= max_lon)

def create_route_map(route_points):
    """Create a Folium map with the route and charging stations"""
    try:
        # Calculate center point
        center_lat = sum(point['lat'] for point in route_points) / len(route_points)
        center_lon = sum(point['lon'] for point in route_points) / len(route_points)
        
        # Create the map with a larger zoom level for better visibility
        m = folium.Map(location=[center_lat, center_lon], zoom_start=9)
        
        # Add markers for source and destination with custom icons
        folium.Marker(
            [route_points[0]['lat'], route_points[0]['lon']],
            popup=f"<b>Start:</b> {route_points[0]['name']}",
            icon=folium.Icon(color='green', icon='play', prefix='fa')
        ).add_to(m)
        
        folium.Marker(
            [route_points[-1]['lat'], route_points[-1]['lon']],
            popup=f"<b>Destination:</b> {route_points[-1]['name']}",
            icon=folium.Icon(color='red', icon='flag-checkered', prefix='fa')
        ).add_to(m)
        
        # Add markers for charging stations with custom icons and popups
        for point in route_points[1:-1]:
            if point.get('is_charging_station'):
                popup_html = f"""
                    <div style='font-family: Arial, sans-serif; font-size: 14px;'>
                        <b>{point['name']}</b><br>
                        <i class='fa fa-bolt'></i> {point['charging_speed']} kW<br>
                        <i class='fa fa-plug'></i> {point['available_ports']} ports available
                    </div>
                """
                folium.Marker(
                    [point['lat'], point['lon']],
                    popup=folium.Popup(popup_html, max_width=200),
                    icon=folium.Icon(color='blue', icon='plug', prefix='fa')
                ).add_to(m)
        
        # Create a line connecting all points
        points = [[point['lat'], point['lon']] for point in route_points]
        
        # Draw the route line
        folium.PolyLine(
            points,
            weight=3,
            color='#3388ff',
            opacity=0.8,
            popup='Route'
        ).add_to(m)
        
        # Add arrow indicators along the route
        line = folium.plugins.AntPath(
            points,
            delay=1000,
            weight=3,
            color='#3388ff',
            pulse_color='#FFFFFF'
        )
        line.add_to(m)
        
        # Add distance circles around charging stations
        for point in route_points[1:-1]:
            if point.get('is_charging_station'):
                folium.Circle(
                    location=[point['lat'], point['lon']],
                    radius=5000,  # 5km radius
                    color='blue',
                    fill=True,
                    opacity=0.2
                ).add_to(m)
        
        # Add fullscreen control
        folium.plugins.Fullscreen().add_to(m)
        
        # Add location control
        folium.plugins.LocateControl().add_to(m)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Save map to a temporary file
        map_path = os.path.join(app.root_path, 'static', 'route_maps')
        os.makedirs(map_path, exist_ok=True)
        map_file = os.path.join(map_path, 'current_route.html')
        
        # Save the map with custom HTML
        m.get_root().html.add_child(folium.Element("""
            <style>
                #map {
                    width: 100% !important;
                    height: 100% !important;
                    position: absolute;
                    top: 0;
                    left: 0;
                }
            </style>
        """))
        m.save(map_file)
        
        return 'route_maps/current_route.html'
        
    except Exception as e:
        print(f"Error creating map: {str(e)}")
        raise

@app.route('/serve_route_map/<path:filename>')
def serve_route_map(filename):
    try:
        directory = os.path.join(app.root_path, 'static', 'route_maps')
        if not os.path.exists(os.path.join(directory, filename)):
            print(f"Map file not found: {filename}")
            return jsonify({"error": "Map file not found"}), 404
        return send_from_directory(directory, filename)
    except Exception as e:
        print(f"Error serving map file {filename}: {str(e)}")
        return jsonify({"error": "Error serving map file"}), 500

@app.route('/driver_behavior')
def driver_behavior():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('driver_behavior.html')

@app.route('/api/driver_behavior', methods=['GET'])
def get_driver_behavior():
    if not session.get('logged_in'):
        return jsonify({'error': 'Not logged in'}), 401
    
    # Generate some behavior data if none exists
    if DriverBehavior.query.count() == 0:
        generate_driver_behavior()
    
    behaviors = DriverBehavior.query.order_by(DriverBehavior.timestamp.desc()).limit(100).all()
    behavior_data = []
    for behavior in behaviors:
        vehicle = Vehicle.query.get(behavior.vehicle_id)
        behavior_data.append({
            'vehicle_name': vehicle.vehicle_name,
            'timestamp': behavior.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'speed': behavior.speed,
            'harsh_braking': behavior.harsh_braking,
            'rapid_acceleration': behavior.rapid_acceleration,
            'idle_time': behavior.idle_time,
            'score': behavior.score
        })
    return jsonify(behavior_data)

@app.route('/maintenance_alerts')
def maintenance_alerts():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('maintenance_alerts.html')

@app.route('/api/maintenance_alerts', methods=['GET'])
def get_maintenance_alerts():
    if not session.get('logged_in'):
        return jsonify({'error': 'Not logged in'}), 401
    
    # Generate some alerts if none exist
    if MaintenanceAlert.query.count() == 0:
        generate_maintenance_alerts()
    
    alerts = MaintenanceAlert.query.order_by(MaintenanceAlert.timestamp.desc()).all()
    alert_data = []
    for alert in alerts:
        vehicle = Vehicle.query.get(alert.vehicle_id)
        alert_data.append({
            'id': alert.id,
            'vehicle_name': vehicle.vehicle_name,
            'alert_type': alert.alert_type,
            'description': alert.description,
            'timestamp': alert.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'priority': alert.priority,
            'status': alert.status
        })
    return jsonify(alert_data)

@app.route('/api/update_alert_status', methods=['POST'])
def update_alert_status():
    # Log the entire request for debugging
    import traceback
    
    # Check if user is logged in
    if not session.get('logged_in'):
        app.logger.error('Unauthorized access attempt to update alert status')
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        # Log raw request data for debugging
        raw_data = request.get_json(force=True)
        app.logger.info(f'Received update alert status request: {raw_data}')
        
        # Extract alert_id and status, with explicit type conversion
        alert_id = raw_data.get('alert_id')
        new_status = raw_data.get('status')
        
        # Comprehensive input validation
        if alert_id is None:
            app.logger.error('Alert ID is None')
            return jsonify({'error': 'Alert ID is required'}), 400
        
        try:
            alert_id = int(alert_id)  # Ensure it's an integer
        except (ValueError, TypeError):
            app.logger.error(f'Invalid alert ID type: {type(alert_id)}')
            return jsonify({'error': 'Invalid alert ID'}), 400
        
        if not new_status:
            app.logger.error('Status is missing or empty')
            return jsonify({'error': 'Status is required'}), 400
        
        # Find the alert
        alert = MaintenanceAlert.query.get(alert_id)
        if not alert:
            app.logger.error(f'Alert with ID {alert_id} not found')
            return jsonify({'error': f'Alert with ID {alert_id} not found'}), 404
        
        # Validate status
        valid_statuses = ['Open', 'Closed']
        if new_status not in valid_statuses:
            app.logger.error(f'Invalid status: {new_status}. Must be one of {valid_statuses}')
            return jsonify({'error': f'Invalid status. Must be one of {valid_statuses}'}), 400
        
        # Update the alert status
        alert.status = new_status
        db.session.commit()
        
        app.logger.info(f'Successfully updated alert {alert_id} to status {new_status}')
        return jsonify({
            'success': True, 
            'message': f'Alert {alert_id} updated to {new_status} status'
        })
    
    except Exception as e:
        # Log the full stack trace
        app.logger.error(f'Unexpected error updating alert status: {str(e)}')
        app.logger.error(traceback.format_exc())
        
        # Rollback the session to prevent any partial commits
        db.session.rollback()
        
        return jsonify({
            'error': f'Unexpected error: {str(e)}',
            'details': traceback.format_exc()
        }), 500

@app.route('/consumption_metrics')
def consumption_metrics():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    try:
        # Get all vehicles
        vehicles = Vehicle.query.all()
        
        # Calculate consumption metrics
        total_vehicles = len(vehicles)
        avg_battery = sum(v.battery_status for v in vehicles) / total_vehicles if total_vehicles > 0 else 0
        
        # Get driver behavior data
        behaviors = DriverBehavior.query.all()
        total_behaviors = len(behaviors)
        avg_score = sum(b.score for b in behaviors) / total_behaviors if total_behaviors > 0 else 0
        
        # Calculate efficiency metrics
        harsh_braking_count = sum(1 for b in behaviors if b.harsh_braking)
        rapid_accel_count = sum(1 for b in behaviors if b.rapid_acceleration)
        
        # Get maintenance alerts
        alerts = MaintenanceAlert.query.all()
        maintenance_count = len(alerts)
        
        # Prepare chart data
        battery_data = [
            {
                'vehicle': v.vehicle_name,
                'battery': v.battery_status,
                'location': v.location
            }
            for v in vehicles
        ]
        
        behavior_data = [
            {
                'vehicle': Vehicle.query.get(b.vehicle_id).vehicle_name,
                'score': b.score,
                'date': b.timestamp.strftime('%Y-%m-%d')
            }
            for b in behaviors
        ]
        
        return render_template(
            'consumption_metrics.html',
            total_vehicles=total_vehicles,
            avg_battery=round(avg_battery, 2),
            avg_score=round(avg_score, 2),
            harsh_braking_count=harsh_braking_count,
            rapid_accel_count=rapid_accel_count,
            maintenance_count=maintenance_count,
            battery_data=battery_data,
            behavior_data=behavior_data
        )
    
    except Exception as e:
        print(f"Error in consumption metrics: {str(e)}")
        flash('Error loading consumption metrics', 'error')
        return redirect(url_for('index'))

@app.route('/consumption')
def consumption_page():
    """Render the consumption and cost analysis page"""
    return render_template('consumption.html')

@app.route('/report_generation')
def report_generation():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('report_generation.html')

@app.route('/api/vehicles')
def get_vehicles():
    if not session.get('logged_in'):
        return jsonify({'error': 'Not logged in'}), 401
    vehicles = Vehicle.query.all()
    return jsonify([{
        'id': v.id,
        'vehicle_name': v.vehicle_name,
        'vehicle_number': v.vehicle_number
    } for v in vehicles])

@app.route('/api/generate_report', methods=['POST'])
def generate_report():
    try:
        data = request.get_json()
        report_type = data.get('report_type')
        start_date = datetime.strptime(data.get('start_date'), '%Y-%m-%d')
        end_date = datetime.strptime(data.get('end_date'), '%Y-%m-%d')
        vehicles = data.get('vehicles', [])

        # Create reports directory if it doesn't exist
        os.makedirs('static/reports', exist_ok=True)

        # Generate report filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'report_{report_type}_{timestamp}.pdf'
        filepath = os.path.join('static/reports', filename)

        # Get data based on report type
        if report_type == 'battery_health':
            report_data = Vehicle.query.filter(Vehicle.id.in_(vehicles)).all()
        elif report_type == 'driver_behavior':
            report_data = db.session.query(DriverBehavior, Vehicle).join(Vehicle).filter(
                DriverBehavior.timestamp.between(start_date, end_date),
                Vehicle.id.in_(vehicles)
            ).all()
        elif report_type == 'maintenance':
            report_data = db.session.query(MaintenanceAlert, Vehicle).join(Vehicle).filter(
                MaintenanceAlert.timestamp.between(start_date, end_date),
                Vehicle.id.in_(vehicles)
            ).all()
        elif report_type == 'consumption':
            report_data = db.session.query(ConsumptionMetric, Vehicle).join(Vehicle).filter(
                ConsumptionMetric.timestamp.between(start_date, end_date),
                Vehicle.id.in_(vehicles)
            ).all()

        # Generate PDF
        headers, rows = format_report_data(report_type, report_data)
        
        doc = SimpleDocTemplate(filepath, pagesize=letter)
        elements = []
        
        # Add title
        styles = getSampleStyleSheet()
        title = report_type.replace('_', ' ').title() + ' Report'
        elements.append(Paragraph(title, styles['Title']))
        elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        elements.append(Paragraph(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}", styles['Normal']))
        
        # Create table
        table_data = [headers] + rows
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)
        
        # Build PDF
        doc.build(elements)

        # Save report info to database
        new_report = Report(
            report_type=report_type,
            filename=filename,
            generated_at=datetime.now()
        )
        db.session.add(new_report)
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Report generated successfully',
            'report_id': new_report.id
        })

    except Exception as e:
        print(f"Error generating report: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error generating report: {str(e)}'
        }), 500

def format_report_data(report_type, data):
    """Format report data based on type"""
    if report_type == 'battery_health':
        headers = ['Vehicle Name', 'Vehicle Number', 'Battery Status', 'Location']
        rows = [
            [
                vehicle.vehicle_name,
                vehicle.vehicle_number,
                f"{vehicle.battery_status}%",
                vehicle.location
            ]
            for vehicle in data
        ]
    
    elif report_type == 'driver_behavior':
        headers = ['Vehicle', 'Date', 'Driver Score', 'Harsh Braking', 'Rapid Acceleration']
        rows = [
            [
                record.Vehicle.vehicle_name,
                record.DriverBehavior.timestamp.strftime('%Y-%m-%d'),
                f"{record.DriverBehavior.score}%",
                'Yes' if record.DriverBehavior.harsh_braking else 'No',
                'Yes' if record.DriverBehavior.rapid_acceleration else 'No'
            ]
            for record in data
        ]
    
    elif report_type == 'maintenance':
        headers = ['Vehicle', 'Alert Type', 'Description', 'Priority', 'Status']
        rows = [
            [
                record.Vehicle.vehicle_name,
                record.MaintenanceAlert.alert_type,
                record.MaintenanceAlert.description,
                record.MaintenanceAlert.priority,
                record.MaintenanceAlert.status
            ]
            for record in data
        ]
    
    elif report_type == 'consumption':
        headers = ['Vehicle', 'Date', 'Energy Used (kWh)', 'Cost', 'Distance (km)']
        rows = [
            [
                record.Vehicle.vehicle_name,
                record.ConsumptionMetric.timestamp.strftime('%Y-%m-%d'),
                f"{record.ConsumptionMetric.energy_used:.2f}",
                f"₹{record.ConsumptionMetric.cost:.2f}",
                f"{record.ConsumptionMetric.distance:.1f}"
            ]
            for record in data
        ]
    
    return headers, rows

@app.route('/api/reports', methods=['GET'])
def get_reports():
    """Get list of generated reports"""
    reports = Report.query.order_by(Report.generated_at.desc()).all()
    return jsonify([{
        'id': report.id,
        'report_type': report.report_type,
        'filename': report.filename,
        'generated_at': report.generated_at.isoformat()
    } for report in reports])

@app.route('/api/reports/<int:report_id>/download')
def download_report(report_id):
    """Download a generated report"""
    report = Report.query.get_or_404(report_id)
    return send_from_directory(
        os.path.join('static', 'reports'),
        report.filename,
        as_attachment=True
    )

@app.route('/api/reports/<int:report_id>', methods=['DELETE'])
def delete_report(report_id):
    """Delete a generated report"""
    try:
        report = Report.query.get_or_404(report_id)
        filepath = os.path.join('static', 'reports', report.filename)
        
        # Delete file if it exists
        if os.path.exists(filepath):
            os.remove(filepath)
        
        # Delete database record
        db.session.delete(report)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Report deleted successfully'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/logout')
def logout():
    session.clear()  # Clear all session data
    return redirect(url_for('login'))

@app.route('/settings')
def settings():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=session.get('username')).first()
    return render_template('settings.html', current_user=user)

@app.route('/api/update_settings', methods=['POST'])
def update_settings():
    if not session.get('logged_in'):
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.get_json()
    user = User.query.filter_by(username=session.get('username')).first()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    try:
        user.email = data.get('email', user.email)
        user.city = data.get('city', user.city)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/change_password', methods=['POST'])
def change_password():
    if not session.get('logged_in'):
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.get_json()
    user = User.query.filter_by(username=session.get('username')).first()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    current_password = data.get('currentPassword')
    new_password = data.get('newPassword')
    
    if user.password != current_password:  # In production, use proper password hashing
        return jsonify({'error': 'Current password is incorrect'}), 401
    
    try:
        user.password = new_password  # In production, hash the password
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/consumption/vehicle/<vehicle_id>', methods=['GET'])
def get_vehicle_consumption(vehicle_id):
    """Get consumption metrics for a specific vehicle or all vehicles"""
    try:
        # Get date range from query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if start_date and end_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        else:
            # Get last 30 days by default
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)

        if vehicle_id == 'all':
            # Query for all vehicles
            metrics = db.session.query(
                ConsumptionMetric, Vehicle
            ).join(Vehicle).filter(
                ConsumptionMetric.timestamp.between(start_date, end_date)
            ).order_by(ConsumptionMetric.timestamp.desc()).all()
        else:
            # Query for specific vehicle
            metrics = db.session.query(
                ConsumptionMetric, Vehicle
            ).join(Vehicle).filter(
                ConsumptionMetric.vehicle_id == vehicle_id,
                ConsumptionMetric.timestamp.between(start_date, end_date)
            ).order_by(ConsumptionMetric.timestamp.desc()).all()

        return jsonify([{
            'vehicle_name': metric.Vehicle.vehicle_name,
            'vehicle_number': metric.Vehicle.vehicle_number,
            'timestamp': metric.ConsumptionMetric.timestamp.isoformat(),
            'energy_used': metric.ConsumptionMetric.energy_used,
            'cost': metric.ConsumptionMetric.cost,
            'distance': metric.ConsumptionMetric.distance,
            'efficiency': metric.ConsumptionMetric.efficiency if metric.ConsumptionMetric.efficiency else 0
        } for metric in metrics])

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/add_consumption')
def add_consumption_page():
    """Render the add consumption data page"""
    return render_template('add_consumption.html')

@app.route('/api/consumption/summary', methods=['GET'])
def get_consumption_summary():
    """Get consumption summary for all vehicles"""
    try:
        # Get date range from query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if start_date and end_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        else:
            # Get last 30 days by default
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)

        # Query for consumption metrics
        metrics = db.session.query(
            Vehicle.vehicle_name,
            Vehicle.vehicle_number,
            func.sum(ConsumptionMetric.energy_used).label('total_energy'),
            func.sum(ConsumptionMetric.cost).label('total_cost'),
            func.sum(ConsumptionMetric.distance).label('total_distance'),
            func.avg(ConsumptionMetric.efficiency).label('avg_efficiency')
        ).join(ConsumptionMetric).filter(
            ConsumptionMetric.timestamp.between(start_date, end_date)
        ).group_by(Vehicle.id).all()

        return jsonify([{
            'vehicle_name': metric.vehicle_name,
            'vehicle_number': metric.vehicle_number,
            'total_energy': round(metric.total_energy, 2) if metric.total_energy else 0,
            'total_cost': round(metric.total_cost, 2) if metric.total_cost else 0,
            'total_distance': round(metric.total_distance, 2) if metric.total_distance else 0,
            'avg_efficiency': round(metric.avg_efficiency, 2) if metric.avg_efficiency else 0
        } for metric in metrics])

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/consumption/add', methods=['POST'])
def add_consumption_metric():
    """Add a new consumption metric"""
    try:
        data = request.get_json()
        vehicle_id = data.get('vehicle_id')
        energy_used = float(data.get('energy_used', 0))
        distance = float(data.get('distance', 0))
        
        # Calculate efficiency (kWh/km)
        efficiency = energy_used / distance if distance > 0 else 0
        
        # Calculate cost (assuming rate of ₹8 per kWh)
        cost = energy_used * 8
        
        metric = ConsumptionMetric(
            vehicle_id=vehicle_id,
            timestamp=datetime.now(),
            energy_used=energy_used,
            cost=cost,
            distance=distance,
            efficiency=efficiency
        )
        
        db.session.add(metric)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Consumption metric added successfully',
            'data': {
                'id': metric.id,
                'timestamp': metric.timestamp.isoformat(),
                'energy_used': metric.energy_used,
                'cost': metric.cost,
                'distance': metric.distance,
                'efficiency': metric.efficiency
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

def calculate_total_distance(route_points):
    """Calculate total distance of the route in kilometers"""
    total_distance = 0
    for i in range(len(route_points) - 1):
        lat1, lon1 = route_points[i]['lat'], route_points[i]['lon']
        lat2, lon2 = route_points[i + 1]['lat'], route_points[i + 1]['lon']
        total_distance += haversine_distance(lat1, lon1, lat2, lon2)
    return total_distance

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points on the earth"""
    R = 6371  # Earth's radius in kilometers

    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'route_maps'), exist_ok=True)
    
    with app.app_context():
        db.create_all()  # Create tables if they don't exist
        
        # Add sample data if database is empty
        if Vehicle.query.count() == 0:
            print("No vehicles found. Creating sample vehicles.")
            # Create sample vehicles
            sample_vehicles = [
                Vehicle(vehicle_name='EV-001',
                        vehicle_number='KA01AB1234', 
                        owner_name='John Doe', 
                        battery_status=75, 
                        location='Bangalore', 
                        speed=0),
                Vehicle(vehicle_name='EV-002',
                        vehicle_number='KA02CD5678', 
                        owner_name='Jane Smith', 
                        battery_status=45, 
                        location='Mysore', 
                        speed=30)
            ]
            db.session.add_all(sample_vehicles)
            db.session.commit()
            
            # Create sample maintenance alerts
            alert1 = MaintenanceAlert(
                vehicle_id=sample_vehicles[0].id,
                alert_type='Battery',
                description='Low battery level detected',
                timestamp=datetime.now(),
                priority='High',
                status='Open'
            )
            alert2 = MaintenanceAlert(
                vehicle_id=sample_vehicles[1].id,
                alert_type='Tire Pressure',
                description='Low tire pressure warning',
                timestamp=datetime.now(),
                priority='Medium',
                status='Open'
            )
            db.session.add_all([alert1, alert2])
            db.session.commit()
            
            # Create sample driver behaviors
            behavior1 = DriverBehavior(
                vehicle_id=sample_vehicles[0].id,
                timestamp=datetime.now(),
                speed=50,
                harsh_braking=True,
                rapid_acceleration=False,
                idle_time=20,
                score=80
            )
            behavior2 = DriverBehavior(
                vehicle_id=sample_vehicles[1].id,
                timestamp=datetime.now(),
                speed=30,
                harsh_braking=False,
                rapid_acceleration=True,
                idle_time=10,
                score=70
            )
            db.session.add_all([behavior1, behavior2])
            db.session.commit()
            
            # Create sample consumption metrics
            metric1 = ConsumptionMetric(
                vehicle_id=sample_vehicles[0].id,
                timestamp=datetime.now(),
                energy_used=10.5,
                cost=315,
                distance=50,
                efficiency=1.7
            )
            metric2 = ConsumptionMetric(
                vehicle_id=sample_vehicles[1].id,
                timestamp=datetime.now(),
                energy_used=8.2,
                cost=246,
                distance=40,
                efficiency=1.2
            )
            db.session.add_all([metric1, metric2])
            db.session.commit()
        
    app.run(debug=True)
