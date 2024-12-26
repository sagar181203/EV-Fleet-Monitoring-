import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2
import requests
import folium
from datetime import datetime
import polyline
import json
import os

class RouteOptimizer:
    def __init__(self):
        self.charging_stations = pd.read_csv('charging_stations_india.csv')
        self.AVERAGE_EV_RANGE = 250  # km on full charge
        self.SAFETY_MARGIN = 0.2  # 20% battery reserve
        self.MAPBOX_TOKEN = "YOUR_MAPBOX_TOKEN"  # Optional: Add your Mapbox token for better routing

    def haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points using Haversine formula"""
        R = 6371  # Earth's radius in kilometers

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c

        return distance

    def get_coordinates(self, address):
        """Get coordinates from address using Nominatim API"""
        try:
            base_url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': f"{address}, India",
                'format': 'json',
                'limit': 1,
                'countrycodes': 'in'
            }
            headers = {
                'User-Agent': 'EV_Fleet_Monitor/1.0'
            }
            
            response = requests.get(base_url, params=params, headers=headers)
            data = response.json()
            
            if data:
                return float(data[0]['lat']), float(data[0]['lon']), data[0].get('display_name', '')
            return None, None, None
        except Exception as e:
            print(f"Error getting coordinates: {e}")
            return None, None, None

    def get_route_from_osrm(self, source_coords, dest_coords):
        """Get route details from OSRM"""
        try:
            base_url = "http://router.project-osrm.org/route/v1/driving"
            url = f"{base_url}/{source_coords[1]},{source_coords[0]};{dest_coords[1]},{dest_coords[0]}"
            params = {
                'overview': 'full',
                'geometries': 'polyline',
                'steps': 'true'
            }
            
            response = requests.get(url, params=params)
            data = response.json()
            
            if data['code'] == 'Ok':
                route = data['routes'][0]
                return {
                    'distance': route['distance'] / 1000,  # Convert to km
                    'duration': route['duration'] / 3600,  # Convert to hours
                    'geometry': route['geometry']
                }
            return None
        except Exception as e:
            print(f"Error getting route: {e}")
            return None

    def find_nearby_stations(self, lat, lon, max_distance=100):
        """Find charging stations within max_distance km"""
        nearby = []
        for _, station in self.charging_stations.iterrows():
            distance = self.haversine_distance(lat, lon, 
                                            station['Latitude'], 
                                            station['Longitude'])
            if distance <= max_distance:
                nearby.append({
                    'station_id': station['Station ID'],
                    'name': station['Station Name'],
                    'city': station['City'],
                    'state': station['State'],
                    'distance': round(distance, 2),
                    'lat': station['Latitude'],
                    'lon': station['Longitude'],
                    'charging_speed': station['Charging Speed (kW)'],
                    'available_ports': station['Available Ports']
                })
        return sorted(nearby, key=lambda x: x['distance'])

    def estimate_charging_time(self, current_battery, target_battery, charging_speed):
        """Estimate charging time in hours"""
        battery_capacity = 75  # kWh (assumed average EV battery capacity)
        energy_needed = (target_battery - current_battery) / 100 * battery_capacity
        return round(energy_needed / charging_speed, 2)

    def optimize_route(self, source_address, dest_address, battery_percentage):
        """Optimize route with charging stations"""
        # Get coordinates
        source_coords = self.get_coordinates(source_address)
        dest_coords = self.get_coordinates(dest_address)
        
        if not source_coords[0] or not dest_coords[0]:
            return {
                'status': 'error',
                'message': 'Could not find coordinates for provided addresses'
            }

        # Get route details
        route_details = self.get_route_from_osrm((source_coords[0], source_coords[1]), 
                                               (dest_coords[0], dest_coords[1]))
        
        if not route_details:
            return {
                'status': 'error',
                'message': 'Could not calculate route'
            }

        total_distance = route_details['distance']
        available_range = (battery_percentage / 100) * self.AVERAGE_EV_RANGE

        # Check if direct route is possible with safety margin
        if available_range >= (total_distance * (1 + self.SAFETY_MARGIN)):
            return {
                'status': 'success',
                'message': 'Direct route possible without charging',
                'source_address': source_coords[2],
                'dest_address': dest_coords[2],
                'distance': round(total_distance, 2),
                'duration': round(route_details['duration'], 2),
                'route': self.create_route_map(source_coords, dest_coords, 
                                            route_details['geometry'])
            }

        # Find charging stations along route
        decoded_polyline = polyline.decode(route_details['geometry'])
        route_points = [(p[0], p[1]) for p in decoded_polyline]
        
        # Sample points along route for finding charging stations
        num_samples = min(5, len(route_points))
        sample_indices = np.linspace(0, len(route_points)-1, num_samples).astype(int)
        
        all_charging_stops = []
        for idx in sample_indices:
            lat, lon = route_points[idx]
            stops = self.find_nearby_stations(lat, lon)
            all_charging_stops.extend(stops)
        
        # Remove duplicates and sort by distance from route
        unique_stops = {stop['station_id']: stop for stop in all_charging_stops}
        charging_stops = sorted(unique_stops.values(), 
                              key=lambda x: x['distance'])[:3]  # Top 3 closest stations

        if not charging_stops:
            return {
                'status': 'warning',
                'message': 'No charging stations found along route',
                'distance': round(total_distance, 2)
            }

        # Calculate charging details for each stop
        for stop in charging_stops:
            stop['charging_time'] = self.estimate_charging_time(
                battery_percentage, 90, stop['charging_speed'])

        return {
            'status': 'success',
            'message': f"Route planned with {len(charging_stops)} charging stops",
            'source_address': source_coords[2],
            'dest_address': dest_coords[2],
            'distance': round(total_distance, 2),
            'duration': round(route_details['duration'], 2),
            'charging_stops': charging_stops,
            'route': self.create_route_map(source_coords, dest_coords, 
                                         route_details['geometry'], charging_stops)
        }

    def create_route_map(self, source, dest, route_geometry, charging_stops=None):
        """Create an HTML map with the route"""
        # Create map centered between source and dest
        center_lat = (source[0] + dest[0]) / 2
        center_lon = (source[1] + dest[1]) / 2
        m = folium.Map(location=[center_lat, center_lon], zoom_start=5)

        # Add source marker
        folium.Marker(
            [source[0], source[1]],
            popup=f'Start: {source[2]}',
            icon=folium.Icon(color='green', icon='info-sign')
        ).add_to(m)

        # Add destination marker
        folium.Marker(
            [dest[0], dest[1]],
            popup=f'Destination: {dest[2]}',
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)

        # Add charging stops if any
        if charging_stops:
            for stop in charging_stops:
                folium.Marker(
                    [stop['lat'], stop['lon']],
                    popup=f"""
                    <b>{stop['name']}</b><br>
                    City: {stop['city']}, {stop['state']}<br>
                    Distance from route: {stop['distance']} km<br>
                    Charging Speed: {stop['charging_speed']} kW<br>
                    Available Ports: {stop['available_ports']}<br>
                    Est. Charging Time: {stop['charging_time']} hours
                    """,
                    icon=folium.Icon(color='blue', icon='plug', prefix='fa')
                ).add_to(m)

        # Draw route line
        route_coords = polyline.decode(route_geometry)
        folium.PolyLine(
            route_coords,
            weight=2,
            color='blue',
            opacity=0.8
        ).add_to(m)

        # Save map
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        map_filename = f'route_{timestamp}.html'
        map_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'route_maps', map_filename)
        os.makedirs(os.path.dirname(map_path), exist_ok=True)
        m.save(map_path)
        
        return f'static/route_maps/{map_filename}'

# Initialize the optimizer
optimizer = RouteOptimizer()