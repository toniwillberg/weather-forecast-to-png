#!/usr/bin/env python3
# wftp.py - Weather Forecast To PNG

# Dependencies:
#
# python3-pip python3-matplotlib python3-requests python3-numpy imagemagick
#
# If something doesn't seem to work, update your system. If it still doesn't work, try to figure
# out what dependency is missing from the list and let the developers know.
#
#

# Recommended simple PNG viewer for verifying the PNG file looks correct: feh
#
#
# Usage: python3 wftp.py CITY -o output.png -c cache.json
#


"""
Weather Forecast to PNG Generator
=================================
Generates device screensaver PNGs with 7-day forecast + today summary.
100% online city lookup. 5min smart cache. Production-ready.

Author: Toni W
"""

import argparse
import json
import os
import gc
import requests
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import numpy as np
from matplotlib.patches import Rectangle
import subprocess

# =============================================================================
# CONFIGURATION
# =============================================================================

class LayoutConfig:
    """Device layout parameters - edit these values"""
    
    # Device dimensions
    DEVICE_WIDTH = 1072
    DEVICE_HEIGHT = 1448
    DPI = 142
    
    # Title section (0.0=bottom, 1.0=top)
    TITLE_Y = 0.95
    TIME_Y = 0.90
    TITLE_FONT_SIZE = 32
    TIME_FONT_SIZE = 16
    
    # 7-day forecast table
    TABLE_HEADER_Y = 0.84
    TABLE_TOP_Y = 0.79
    TABLE_ROW_HEIGHT = 0.055
    TABLE_COL_X = [0.08, 0.32, 0.62, 0.89]  # Date, Temp, Precip
    
    # TODAY summary box
    TODAY_TOP_Y = 0.34
    TODAY_BOTTOM_Y = 0.16
    TODAY_FONT_SIZE = 28
    TODAY_BORDER_X = 0.16
    TODAY_BORDER_WIDTH = 0.68
    
    # Bottom temperature indicator
    TEMP_LINE_Y = 0.08
    
    # Cache settings
    CACHE_DURATION_MIN = 5




class WFTP:
    """Weather Forecast To PNG main class"""
    
    def __init__(self, city: str, output: str, cache: str):
        self.city = city
        self.output = output
        self.cache = cache
        self.config = LayoutConfig()
        
    def get_device_dimensions(self):
        """Calculate figure size from device specs"""
        w = float(self.config.DEVICE_WIDTH) / self.config.DPI
        h = float(self.config.DEVICE_HEIGHT) / self.config.DPI
        return w, h
    
    def geocode_city(self, city_name: str) -> tuple[float, float, str]:
        """Get latitude, longitude, display name via online lookup"""
        print(f"🔍 Looking up: {city_name}")
        
        # Primary: Open-Meteo Geocoding API
        try:
            url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1&format=json"
            resp = requests.get(url, verify=False, timeout=10).json()
            
            if resp.get('results'):
                result = resp['results'][0]
                lat, lon = result['latitude'], result['longitude']
                display = f"{result.get('name', city_name)}, {result.get('country', '')}".strip(', ')
                print(f"✅ Found: {display} ({lat:.4f}, {lon:.4f})")
                return lat, lon, display
        except Exception as e:
            print(f"⚠️ Open-Meteo failed: {e}")
            
        # Fallback: Nominatim (OpenStreetMap)
        try:
            url = f"https://nominatim.openstreetmap.org/search?q={city_name}&format=json&limit=1"
            resp = requests.get(url, headers={'User-Agent': 'wftp-script'}, 
                            verify=False, timeout=10).json()
            if resp:
                lat, lon = float(resp[0]['lat']), float(resp[0]['lon'])
                display = resp[0].get('display_name', city_name).split(',')[0]
                print(f"✅ Nominatim: {display} ({lat:.4f}, {lon:.4f})")
                return lat, lon, display
        except Exception as e:
            print(f"⚠️ Nominatim failed: {e}")
            
        # Emergency fallback
        print(f"⚠️ Using default country for '{city_name}'")
        return 13.7563, 100.5018, city_name.title()
            
        # Emergency fallback
        print(f"⚠️ Using default country for '{city_name}'")
        return 13.7563, 100.5018, city_name.title()
        
    def load_cache(self) -> tuple[dict | None, datetime | None]:
        """Load weather cache if fresh (within CACHE_DURATION_MIN)"""
        if not os.path.exists(self.cache):
            return None, None
        
        try:
            with open(self.cache, 'r') as f:
                cache = json.load(f)
            cache_time = datetime.fromisoformat(cache['fetch_time'])
            
            if datetime.now() - cache_time < timedelta(minutes=self.config.CACHE_DURATION_MIN):
                print(f"✅ Cache valid: {datetime.now() - cache_time}")
                return cache['data'], cache_time
            else:
                print("📅 Cache expired")
        except Exception:
            print("❌ Cache corrupt")
        
        return None, None
    
    def save_cache(self, data: dict, fetch_time: datetime):
        """Save weather data + timestamp to cache"""
        cache = {
            'fetch_time': fetch_time.isoformat(), 
            'data': data
        }
        with open(self.cache, 'w') as f:
            json.dump(cache, f)
    
    def fetch_weather(self, lat: float, lon: float) -> dict:
        """Fetch fresh weather data from Open-Meteo"""
        url = ("https://api.open-meteo.com/v1/forecast?"
               f"latitude={lat}&longitude={lon}&"
               "hourly=temperature_2m,precipitation_probability&"
               "daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&"
               "timezone=auto&forecast_days=7")
        
        resp = requests.get(url, verify=False, timeout=10).json()
        return resp
    
    def parse_weather_data(self, weather_data: dict):
        """Extract and format weather data for display"""
        hourly = weather_data['hourly']
        daily = weather_data['daily']
        
        # Hourly data (first 24h = today)
        hours = [datetime.fromisoformat(t) for t in hourly['time']]
        today_temps = np.array(hourly['temperature_2m'])[:24]
        today_precip = np.array(hourly['precipitation_probability'])[:24]
        
        # Daily data (7 days)
        daily_max = daily['temperature_2m_max']
        daily_min = daily['temperature_2m_min']
        daily_precip = daily['precipitation_probability_max']
        daily_dates = [datetime.fromisoformat(daily['time'][i]).strftime('%a') 
                      for i in range(7)]
        
        return {
            'today_avg_temp': float(np.mean(today_temps)),
            'today_precip': float(np.mean(today_precip)),
            'daily': {
                'dates': daily_dates,
                'max': daily_max,
                'min': daily_min,
                'precip': daily_precip
            }
        }
    
    def create_plot(self, display_city: str, fetch_time_str: str, weather_data: dict):
        """Generate the complete weather PNG"""
        fig_width, fig_height = self.get_device_dimensions()
        
        fig = plt.figure(figsize=(fig_width, fig_height), dpi=self.config.DPI)
        ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
        fig.patch.set_facecolor('white')
        ax.set_facecolor('white')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        
        self._draw_title(ax, display_city, fetch_time_str)
        self._draw_forecast_table(ax, weather_data['daily'])
        self._draw_today_box(ax, weather_data['today_avg_temp'], weather_data['today_precip'])
        self._draw_temp_line(ax)
        
        # Save plot
        fig.savefig(self.output, facecolor='white', dpi=self.config.DPI, 
                bbox_inches='tight', transparent=False, pad_inches=0)

        # Resize the image to the desired dimensions
        subprocess.run(["convert", self.output, 
                    f"-resize", f"{self.config.DEVICE_WIDTH}x{self.config.DEVICE_HEIGHT}", 
                    "-colorspace", "Gray", 
                    "-colors", "16", 
                    "-depth", "8", 
                    self.output])
                    
        plt.close(fig)
        gc.collect()
        
    def _draw_title(self, ax, city: str, time_str: str):
        """Draw title and timestamp"""
        ax.text(0.5, self.config.TITLE_Y, f"{city} WEATHER", 
            ha='center', va='top', fontsize=self.config.TITLE_FONT_SIZE, 
            fontweight='bold')
        fetch_time = datetime.now()
        ax.text(0.95, self.config.TIME_Y, fetch_time.strftime('%Y-%m-%d %H:%M'), 
            ha='right', va='top', fontsize=self.config.TIME_FONT_SIZE * 0.5, 
            color='gray', fontweight='normal')  # make it 50% smaller and normal weight
        ax.text(0.5, self.config.TABLE_HEADER_Y, '7-DAY FORECAST', 
            ha='center', va='bottom', fontsize=22, fontweight='bold')
    
    def _draw_forecast_table(self, ax, daily_data: dict):
        """Draw 7-day forecast table with alternating row colors"""
        col_x = self.config.TABLE_COL_X
        row_height = self.config.TABLE_ROW_HEIGHT
        table_top = self.config.TABLE_TOP_Y
        
        for i in range(7):
            y_pos = table_top - (i * row_height)
            
            # Alternating row background
            if i % 2 == 0:
                ax.add_patch(Rectangle(
                    (0.05, y_pos - row_height/2), 0.9, row_height,
                    facecolor='#f0f0f0', alpha=0.9, transform=ax.transData
                ))
            
            # Date
            ax.text(col_x[0], y_pos, daily_data['dates'][i], 
                   ha='left', va='center', fontsize=20, fontweight='bold')
            # Temperature range
            ax.text(col_x[1], y_pos, 
                   f"{daily_data['max'][i]:.0f}/{daily_data['min'][i]:.0f}°C",
                   ha='center', va='center', fontsize=22, fontweight='bold')
            # Precipitation
            ax.text(col_x[2], y_pos, f"{daily_data['precip'][i]}%", 
                   ha='center', va='center', fontsize=20)
    
    def _draw_today_box(self, ax, avg_temp: float, precip: float):
        """Draw highlighted TODAY summary box"""
        top_y, bottom_y = self.config.TODAY_TOP_Y, self.config.TODAY_BOTTOM_Y
        height = top_y - bottom_y
        
        # Border
        border = Rectangle((self.config.TODAY_BORDER_X, bottom_y), 
                          self.config.TODAY_BORDER_WIDTH, height,
                          linewidth=3, edgecolor='black', facecolor='white',
                          transform=ax.transData)
        ax.add_patch(border)
        
        # Text
        ax.text(0.5, top_y - 0.035, 'TODAY', ha='center', va='top',
               fontsize=self.config.TODAY_FONT_SIZE, fontweight='bold')
        ax.text(0.5, top_y - 0.095, f'{avg_temp:.0f}°C', ha='center', va='center',
               fontsize=self.config.TODAY_FONT_SIZE, fontweight='bold')
        ax.text(0.5, top_y - 0.165, f'Rain: {precip:.0f}%', ha='center', va='center',
               fontsize=self.config.TODAY_FONT_SIZE)
    
    def _draw_temp_line(self, ax):
        """Draw bottom temperature indicator line"""
        ax.plot([0.1, 0.9], [self.config.TEMP_LINE_Y, self.config.TEMP_LINE_Y],
               color='black', linewidth=12, solid_capstyle='round')
    
    def run(self):
        """Main execution workflow"""
        print(f"🌤️ wftp.py - Weather Forecast To PNG")
        print(f"📐 Device: {self.config.DEVICE_WIDTH}x{self.config.DEVICE_HEIGHT}@{self.config.DPI}DPI")
        print(f"🌍 City: {self.city} | 📁 Output: {self.output} | 💾 Cache: {self.cache}")
        
        # 1. Geocode city
        lat, lon, display_city = self.geocode_city(self.city)
        
        # 2. Load cache or fetch fresh weather
        cached_data, cached_time = self.load_cache()
        if cached_data:
            fetch_time_str = cached_time.strftime('%d/%m %H:%M')
            print(f"📁 Cache hit: {fetch_time_str}")
            weather_resp = cached_data
        else:
            print("🌐 Fetching fresh weather...")
            weather_resp = self.fetch_weather(lat, lon)
            fetch_time = datetime.now()
            self.save_cache(weather_resp, fetch_time)
            fetch_time_str = fetch_time.strftime('%d/%m %H:%M')
            print(f"✅ Cached: {fetch_time_str}")
        
        # 3. Parse weather data
        parsed_data = self.parse_weather_data(weather_resp)
        
        # 4. Generate PNG
        self.create_plot(display_city, fetch_time_str, parsed_data)
        
        # 5. Report results
        size_kb = os.path.getsize(self.output) // 1024
        print(f"✅ Saved: {os.path.abspath(self.output)} ({size_kb} KB)")
        print(f"🌍 {display_city} | Data: {fetch_time_str}")


def main():
    """Entry point with CLI parsing"""
    parser = argparse.ArgumentParser(description='Weather Forecast To PNG - Device Screensaver')
    parser.add_argument('city', help='City name (REQUIRED)')
    parser.add_argument('-o', '--output', required=True, help='Output PNG file (REQUIRED)')
    parser.add_argument('-c', '--cache', required=True, help='Cache file (REQUIRED)')
    args = parser.parse_args()
    
    app = WFTP(args.city, args.output, args.cache)
    app.run()


if __name__ == '__main__':
    main()

