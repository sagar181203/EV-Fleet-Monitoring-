# EV Fleet Monitoring System

A comprehensive web-based system for monitoring and managing electric vehicle fleets, including battery health prediction, route optimization, and maintenance alerts.

## Features

- **Real-time Fleet Monitoring**: Track and monitor your EV fleet in real-time
- **Battery Health Prediction**: ML-powered battery health monitoring and prediction
- **Route Optimization**: Smart route planning considering charging stations and battery capacity
- **Maintenance Alerts**: Proactive maintenance notifications and alerts
- **Report Generation**: Detailed fleet performance and health reports
- **Charging Station Mapping**: Integration with charging station locations in India

## Tech Stack

- **Backend**: Python, Flask
- **Frontend**: HTML, CSS, JavaScript
- **Machine Learning**: Scikit-learn (Battery Health Prediction Model)
- **Data Storage**: CSV files, SQLite
- **Visualization**: JavaScript charting libraries

## Project Structure

```
EV_Fleet_Monitoring/
├── app.py                         # Main Flask application
├── route_model.py                 # Route optimization model
├── route_optimizer.py             # Route optimization logic
├── train_model.py                 # ML model training script
├── static/                        # Static assets (CSS, JS, images)
├── templates/                     # HTML templates
├── Dataset.csv                    # Training dataset
├── battery_health_model.pkl       # Trained ML model
├── charging_stations_india.csv    # Charging station data
└── requirements.txt               # Project dependencies
```

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Run the application:
   ```
   python app.py
   ```

## Usage

1. Access the web interface at `http://localhost:5000`
2. Use the dashboard to:
   - Monitor fleet status
   - Check battery health predictions
   - Plan optimized routes
   - Generate performance reports
   - View maintenance alerts

## Data Sources

- Battery health data: Custom dataset for ML model training
- Charging station data: Curated dataset of charging stations in India
- Route information: Real-time fleet tracking data

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
