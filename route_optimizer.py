import requests
import json
import math
import folium
import os
import time
from datetime import datetime
from typing import Dict, List, Tuple, Any

class RouteOptimizer:
    def __init__(self):
        self.mapbox_token = 'pk.eyJ1IjoiZXZmbGVldG1vbml0b3IiLCJhIjoiY2xwMHgwOXhpMDJxbTJqbXdsMm91MmJvaSJ9.UEmq5TvzHNjhRGAGj2fWrQ'
        self.charging_stations = [
            {"name": "Charging Station 1", "latitude": 19.0760, "longitude": 72.8777},  # Mumbai
            {"name": "Charging Station 2", "latitude": 18.5204, "longitude": 73.8567},  # Pune
            {"name": "Charging Station 3", "latitude": 21.1458, "longitude": 79.0882},  # Nagpur
            {"name": "Charging Station 4", "latitude": 22.7196, "longitude": 75.8577},  # Indore
            {"name": "Charging Station 5", "latitude": 23.2599, "longitude": 77.4126},  # Bhopal
            {"name": "Charging Station 6", "latitude": 28.7041, "longitude": 77.1025},  # Delhi
            {"name": "Charging Station 7", "latitude": 26.8467, "longitude": 80.9462},  # Lucknow
            {"name": "Charging Station 8", "latitude": 25.5941, "longitude": 85.1376},  # Patna
            {"name": "Charging Station 9", "latitude": 22.5726, "longitude": 88.3639},  # Kolkata
        ]

    def geocode_location(self, location: str) -> Tuple[float, float]:
        """Convert location string to coordinates using Mapbox Geocoding API"""
        try:
            url = f'https://api.mapbox.com/geocoding/v5/mapbox.places/{location}.json'
            params = {
                'access_token': self.mapbox_token,
                'limit': 1,
                'country': 'IN'
            }
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            if not data['features']:
                raise ValueError(f"Location not found: {location}")
            
            feature = data['features'][0]
            return feature['center'][0], feature['center'][1]  # longitude, latitude
        except Exception as e:
            raise Exception(f"Error geocoding location '{location}': {str(e)}")

    def calculate_distance(self, coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        """Calculate distance between two coordinates using Haversine formula"""
        lon1, lat1 = coord1
        lon2, lat2 = coord2
        
        R = 6371  # Earth's radius in kilometers
        
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        return R * c

    def find_nearest_charging_stations(self, route_coordinates: List[List[float]], battery_percentage: float) -> List[Dict]:
        """Find charging stations near the route based on battery percentage"""
        charging_stops = []
        max_distance = 300 * (battery_percentage / 100)  # Assume 300km is max range at 100% battery
        
        current_distance = 0
        last_charging_point = route_coordinates[0]
        
        for i in range(1, len(route_coordinates)):
            segment_distance = self.calculate_distance(
                (route_coordinates[i-1][0], route_coordinates[i-1][1]),
                (route_coordinates[i][0], route_coordinates[i][1])
            )
            current_distance += segment_distance
            
            if current_distance >= max_distance * 0.8:  # Look for charging station when battery is at 20%
                # Find nearest charging station to current point
                min_distance = float('inf')
                nearest_station = None
                
                for station in self.charging_stations:
                    station_coord = (station['longitude'], station['latitude'])
                    distance = self.calculate_distance(
                        (route_coordinates[i][0], route_coordinates[i][1]),
                        station_coord
                    )
                    if distance < min_distance:
                        min_distance = distance
                        nearest_station = station
                
                if nearest_station and min_distance <= 50:  # Only add if station is within 50km of route
                    charging_stops.append({
                        'name': nearest_station['name'],
                        'latitude': nearest_station['latitude'],
                        'longitude': nearest_station['longitude'],
                        'distance': min_distance
                    })
                    last_charging_point = (nearest_station['longitude'], nearest_station['latitude'])
                    current_distance = 0
        
        return charging_stops

    def create_route_map(self, route_coords, charging_stations=None):
        """Create a Folium map with the route and charging stations."""
        try:
            # Get the center point of the route
            center_lat = sum(coord[0] for coord in route_coords) / len(route_coords)
            center_lon = sum(coord[1] for coord in route_coords) / len(route_coords)

            # Create the map centered on the route
            m = folium.Map(location=[center_lat, center_lon], zoom_start=6)

            # Add the route line
            folium.PolyLine(
                locations=route_coords,
                weight=4,
                color='#3388ff',
                opacity=0.8
            ).add_to(m)

            # Add markers for start and end points
            folium.Marker(
                location=route_coords[0],
                popup='<div style="font-size: 14px;"><strong>Start Location</strong></div>',
                icon=folium.Icon(color='green', icon='flag', prefix='fa')
            ).add_to(m)
            
            folium.Marker(
                location=route_coords[-1],
                popup='<div style="font-size: 14px;"><strong>Destination</strong></div>',
                icon=folium.Icon(color='red', icon='flag-checkered', prefix='fa')
            ).add_to(m)

            # Add charging station markers if available
            if charging_stations:
                for station in charging_stations:
                    popup_html = f"""
                    <div style="font-size: 14px; line-height: 1.5;">
                        <strong>{station['name']}</strong><br>
                        Distance from route: {station['distance']:.2f} km
                    </div>
                    """
                    folium.Marker(
                        location=[station['latitude'], station['longitude']],
                        popup=folium.Popup(popup_html, max_width=300),
                        icon=folium.Icon(color='blue', icon='plug', prefix='fa')
                    ).add_to(m)

            # Save the map
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            map_filename = f'route_{current_time}.html'
            map_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'route_maps', map_filename)
            os.makedirs(os.path.dirname(map_path), exist_ok=True)
            m.save(map_path)
            
            return f'static/route_maps/{map_filename}'  # Return the relative path as it was before
            
        except Exception as e:
            print(f"Error creating route map: {str(e)}")
            raise

    def optimize_route(self, source: str, destination: str, battery_percentage: float) -> Dict[str, Any]:
        """Get optimized route with charging stations"""
        try:
            # Convert locations to coordinates
            source_coord = self.geocode_location(source)
            dest_coord = self.geocode_location(destination)
            
            # Get route from Mapbox Directions API
            coords = f"{source_coord[0]},{source_coord[1]};{dest_coord[0]},{dest_coord[1]}"
            url = f'https://api.mapbox.com/directions/v5/mapbox/driving/{coords}'
            params = {
                'access_token': self.mapbox_token,
                'geometries': 'geojson',
                'overview': 'full'
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            if not data['routes']:
                raise ValueError("No route found between the specified locations")
            
            route = data['routes'][0]
            route_coordinates = route['geometry']['coordinates']
            
            # Find charging stations along the route
            charging_stops = self.find_nearest_charging_stations(route_coordinates, battery_percentage)
            
            # Calculate total distance and duration
            total_distance = route['distance'] / 1000  # Convert to kilometers
            duration = route['duration'] / 3600  # Convert to hours

            # Get addresses for source and destination
            source_data = requests.get(f'https://api.mapbox.com/geocoding/v5/mapbox.places/{source_coord[0]},{source_coord[1]}.json',
                                     params={'access_token': self.mapbox_token}).json()
            dest_data = requests.get(f'https://api.mapbox.com/geocoding/v5/mapbox.places/{dest_coord[0]},{dest_coord[1]}.json',
                                   params={'access_token': self.mapbox_token}).json()

            source_address = source_data['features'][0]['place_name'] if source_data['features'] else source
            dest_address = dest_data['features'][0]['place_name'] if dest_data['features'] else destination

            # Create and save the route map
            route_map_filename = self.create_route_map(
                [[coord[1], coord[0]] for coord in route_coordinates],  # Convert to [lat, lon] format
                charging_stops
            )

            message = 'Direct route possible without charging' if not charging_stops else f'Route found with {len(charging_stops)} charging stops'

            return {
                'source_address': source_address,  # Fix: Use the geocoded addresses
                'dest_address': dest_address,
                'distance': total_distance,
                'duration': duration,
                'message': message,
                'route': route_map_filename,
                'charging_stations': charging_stops
            }
            
        except Exception as e:
            raise Exception(f"Error optimizing route: {str(e)}")

# Initialize the optimizer
optimizer = RouteOptimizer()
