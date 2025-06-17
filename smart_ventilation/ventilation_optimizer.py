import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
import logging
import os

class VentilationOptimizer:
    def __init__(self, datasets_path="datasets"):
        """Initialize with historical data files"""
        self.datasets_path = datasets_path
        self.load_historical_data()
        
        # Optimal ranges for classroom comfort
        self.optimal_temp_range = (20, 22)  # °C
        self.optimal_co2_range = (400, 800)  # ppm
        self.optimal_humidity_range = (45, 55)  # %
        
        # Calculate Class B averages from historical data
        self.calculate_class_b_averages()
        
    def load_historical_data(self):
        """Load historical data from CSV files"""
        try:
            temp_file = os.path.join(self.datasets_path, "10c_temp_last_30_days.csv")
            co2_file = os.path.join(self.datasets_path, "10c_co2_last_30_days.csv")
            
            self.temp_data = pd.read_csv(temp_file)
            self.co2_data = pd.read_csv(co2_file)
            
            # Convert time columns to datetime
            self.temp_data['time'] = pd.to_datetime(self.temp_data['time'])
            self.co2_data['time'] = pd.to_datetime(self.co2_data['time'])
            
            logging.info("Historical data loaded successfully")
            
        except Exception as e:
            logging.error(f"Error loading historical data: {e}")
            # Fallback to default values if files don't exist
            self.temp_data = pd.DataFrame({'temperature': [22.0]})
            self.co2_data = pd.DataFrame({'co2': [600.0], 'humidity': [50.0]})
    
    def calculate_class_b_averages(self):
        """Calculate average values from historical data for Class B"""
        try:
            # Average temperature
            self.class_b_avg_temp = self.temp_data['temperature'].mean()
            
            # Average CO2 and humidity
            self.class_b_avg_co2 = self.co2_data['co2'].mean()
            self.class_b_avg_humidity = self.co2_data['humidity'].mean()
            
            logging.info(f"Class B Average Values - Temp: {self.class_b_avg_temp:.2f}°C, "
                        f"CO2: {self.class_b_avg_co2:.2f}ppm, Humidity: {self.class_b_avg_humidity:.2f}%")
            
        except Exception as e:
            logging.error(f"Error calculating averages: {e}")
            # Fallback values
            self.class_b_avg_temp = 22.0
            self.class_b_avg_co2 = 600.0
            self.class_b_avg_humidity = 50.0
    
    def get_class_data(self, mqtt_client):
        """Get data for both classes - A (real-time) and B (averages)"""
        try:
            # Class A: Real-time data from MQTT
            if (hasattr(mqtt_client, "combined_data") and 
                mqtt_client.combined_data and 
                mqtt_client.combined_data.get("temperature") and
                mqtt_client.combined_data.get("humidity") and
                mqtt_client.combined_data.get("co2")):
                
                class_a_data = {
                    "name": "Klassenraum 10c",
                    "temperature": float(mqtt_client.combined_data.get("temperature", [22])[-1]),
                    "humidity": float(mqtt_client.combined_data.get("humidity", [55])[-1]),
                    "co2": float(mqtt_client.combined_data.get("co2", [600])[-1]),
                    "data_source": "mqtt_live"
                }
            else:
                # Fallback for Class A if no MQTT data
                class_a_data = {
                    "name": "Klassenraum 10c",
                    "temperature": 22.0,
                    "humidity": 55.0,
                    "co2": 600.0,
                    "data_source": "fallback"
                }
            
            # Class B: Historical averages
            class_b_data = {
                "name": "Klassenraum 9b",
                "temperature": float(self.class_b_avg_temp),
                "humidity": float(self.class_b_avg_humidity),
                "co2": float(self.class_b_avg_co2),
                "data_source": "historical_average"
            }
            
            return class_a_data, class_b_data
            
        except Exception as e:
            logging.error(f"Error getting class data: {e}")
            # Return fallback data
            return (
                {"name": "Klassenraum 10c", "temperature": 22.0, "humidity": 55.0, "co2": 600.0, "data_source": "error_fallback"},
                {"name": "Klassenraum 9b", "temperature": 22.0, "humidity": 50.0, "co2": 600.0, "data_source": "error_fallback"}
            )
    
    def calculate_comfort_score(self, temp, co2, humidity):
        """Calculate comfort score (0-100) based on optimal ranges"""
        try:
            score = 0
            
            # Temperature score (25 points max)
            temp_min, temp_max = self.optimal_temp_range
            if temp_min <= temp <= temp_max:
                temp_score = 25
            elif temp_min - 2 <= temp <= temp_max + 2:
                temp_score = 15
            else:
                temp_score = 5
            
            # CO2 score (35 points max - most important)
            co2_min, co2_max = self.optimal_co2_range
            if co2_min <= co2 <= co2_max:
                co2_score = 35
            elif co2 < 1000:
                co2_score = 20
            else:
                co2_score = 5
            
            # Humidity score (25 points max)
            hum_min, hum_max = self.optimal_humidity_range
            if hum_min <= humidity <= hum_max:
                hum_score = 25
            elif 40 <= humidity <= 60:
                hum_score = 15
            else:
                hum_score = 5
            
            # Air quality bonus (15 points max)
            air_quality_score = 15
            if co2 > 1000:
                air_quality_score = 5
            elif co2 > 800:
                air_quality_score = 10
            
            total_score = temp_score + co2_score + hum_score + air_quality_score
            
            return min(100, total_score)
            
        except Exception as e:
            logging.error(f"Error calculating comfort score: {e}")
            return 50  # Neutral score on error
    
    def get_competition_data(self, mqtt_client):
        """Get formatted data for the football competition"""
        try:
            class_a_data, class_b_data = self.get_class_data(mqtt_client)
            
            # Calculate scores
            class_a_data["score"] = self.calculate_comfort_score(
                class_a_data["temperature"],
                class_a_data["co2"],
                class_a_data["humidity"]
            )
            
            class_b_data["score"] = self.calculate_comfort_score(
                class_b_data["temperature"],
                class_b_data["co2"],
                class_b_data["humidity"]
            )
            
            return {
                "team_a": class_a_data,
                "team_b": class_b_data
            }
            
        except Exception as e:
            logging.error(f"Error getting competition data: {e}")
            # Return fallback competition data
            return {
                "team_a": {
                    "name": "Klassenraum 10c",
                    "temperature": 22.0,
                    "humidity": 55.0,
                    "co2": 600.0,
                    "score": 75,
                    "data_source": "error_fallback"
                },
                "team_b": {
                    "name": "Klassenraum 9b",
                    "temperature": 21.0,
                    "humidity": 50.0,
                    "co2": 580.0,
                    "score": 80,
                    "data_source": "error_fallback"
                }
            }