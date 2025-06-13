import os
import pandas as pd
import numpy as np
from pymavlink import mavutil
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.table import Table
import math

# Video generation imports
try:
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    from mpl_toolkits.mplot3d import Axes3D
    import cv2
    from PIL import Image, ImageDraw, ImageFont
    import requests
    from io import BytesIO
    VIDEO_AVAILABLE = True
except ImportError as e:
    VIDEO_AVAILABLE = False
    missing_packages = str(e)

console = Console()

class DroneKMLGenerator:
    def __init__(self):
        self.kml_root = None
        self.document = None
        
    def create_kml_structure(self, flight_name):
        """Create the basic KML structure"""
        self.kml_root = ET.Element("kml")
        self.kml_root.set("xmlns", "http://www.opengis.net/kml/2.2")
        self.kml_root.set("xmlns:gx", "http://www.google.com/kml/ext/2.2")
        
        self.document = ET.SubElement(self.kml_root, "Document")
        
        # Document name
        name = ET.SubElement(self.document, "name")
        name.text = f"Drone FPV Flight - {flight_name}"
        
        # Description
        description = ET.SubElement(self.document, "description")
        description.text = f"First-Person View flight path for {flight_name}. Use the tour for immersive FPV experience!"
        
        # Add styles
        self._add_styles()        
    def _add_styles(self):
        """Add KML styles for flight path and waypoints"""
        
        # Flight path style - floating line at altitude
        path_style = ET.SubElement(self.document, "Style")
        path_style.set("id", "flightPath")
        
        line_style = ET.SubElement(path_style, "LineStyle")
        color = ET.SubElement(line_style, "color")
        color.text = "ff0099ff"  # Bright orange line for visibility
        width = ET.SubElement(line_style, "width")
        width.text = "5"  # Thicker line for better visibility
        
        # No fill for polygon (ensures it's just a line)
        poly_style = ET.SubElement(path_style, "PolyStyle")
        fill = ET.SubElement(poly_style, "fill")
        fill.text = "0"
        outline = ET.SubElement(poly_style, "outline")
        outline.text = "1"
    def parse_flight_data(self, bin_path):
        """Parse BIN file and extract comprehensive flight data"""
        console.print(f"📂 [bold blue]Parsing BIN file:[/bold blue] {os.path.basename(bin_path)}")
        
        log = mavutil.mavlink_connection(bin_path)
        
        # Collect different message types
        attitude_data = []  # AHR2 messages for attitude
        gps_data = []       # GPS messages for position and altitude
        
        with Progress(
            SpinnerColumn(), 
            TextColumn("[progress.description]{task.description}"),
            BarColumn(), 
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        ) as progress:
            task = progress.add_task("Parsing flight data", total=None)
            
            while True:
                msg = log.recv_match()
                if msg is None:
                    break
                
                msg_dict = msg.to_dict()
                
                # Collect GPS data (for accurate position and altitude)
                if msg_dict.get('mavpackettype') == 'GPS':
                    if all(key in msg_dict for key in ['Lat', 'Lng', 'Alt']) and \
                       msg_dict['Lat'] != 0 and msg_dict['Lng'] != 0:
                        gps_data.append({
                            'timestamp': msg_dict.get('TimeUS', 0) / 1000000.0,
                            'lat': msg_dict['Lat'],
                            'lng': msg_dict['Lng'], 
                            'alt': msg_dict['Alt'],  # GPS altitude (absolute)
                            'spd': msg_dict.get('Spd', 0),
                            'gcrs': msg_dict.get('GCrs', 0),  # Ground course
                            'vz': msg_dict.get('VZ', 0)       # Vertical velocity
                        })
                
                # Collect attitude data (for orientation)
                elif msg_dict.get('mavpackettype') == 'AHR2':
                    if all(key in msg_dict for key in ['Roll', 'Pitch', 'Yaw']):
                        attitude_data.append({
                            'timestamp': msg_dict.get('TimeUS', 0) / 1000000.0,
                            'roll': msg_dict['Roll'],
                            'pitch': msg_dict['Pitch'],
                            'yaw': msg_dict['Yaw']
                        })
                
                progress.update(task, advance=1)
        
        # Convert to DataFrames
        gps_df = pd.DataFrame(gps_data)
        attitude_df = pd.DataFrame(attitude_data)
        
        if gps_df.empty:
            console.print("⚠️ [yellow]No GPS data found in BIN file[/yellow]")
            return None
            
        if attitude_df.empty:
            console.print("⚠️ [yellow]No attitude data found in BIN file[/yellow]")
            return None
        
        # Sort by timestamp
        gps_df = gps_df.sort_values('timestamp').reset_index(drop=True)
        attitude_df = attitude_df.sort_values('timestamp').reset_index(drop=True)
        
        # Interpolate attitude data to match GPS timestamps
        combined_data = []
        
        for _, gps_row in gps_df.iterrows():
            gps_time = gps_row['timestamp']
            
            # Find closest attitude data
            time_diffs = np.abs(attitude_df['timestamp'] - gps_time)
            closest_idx = time_diffs.idxmin()
            
            if time_diffs.iloc[closest_idx] < 1.0:  # Within 1 second
                attitude_row = attitude_df.iloc[closest_idx]
                
                combined_data.append({
                    'timestamp': gps_time,
                    'lat': gps_row['lat'],
                    'lng': gps_row['lng'],
                    'alt': gps_row['alt'],
                    'spd': gps_row['spd'],
                    'gcrs': gps_row['gcrs'],
                    'vz': gps_row['vz'],
                    'roll': attitude_row['roll'],
                    'pitch': attitude_row['pitch'],
                    'yaw': attitude_row['yaw']
                })
        
        combined_df = pd.DataFrame(combined_data)
        
        console.print(f"✔️ [green]Combined {len(combined_df)} GPS+Attitude points[/green]")
        console.print(f"📊 [cyan]Altitude range: {combined_df['alt'].min():.1f}m to {combined_df['alt'].max():.1f}m[/cyan]")
        
        return combined_df        
    def create_flight_path(self, df, flight_name):
        """Create the main flight path in KML"""
        if df is None or df.empty:
            return
            
        # Create folder for this flight
        flight_folder = ET.SubElement(self.document, "Folder")
        folder_name = ET.SubElement(flight_folder, "name")
        folder_name.text = flight_name
        
        # Flight path placemark for reference
        path_placemark = ET.SubElement(flight_folder, "Placemark")
        path_name = ET.SubElement(path_placemark, "name")
        path_name.text = f"{flight_name} - Reference Path"
        
        path_description = ET.SubElement(path_placemark, "description")
        path_description.text = f"Flight path reference with {len(df)} GPS points"
        
        path_style_url = ET.SubElement(path_placemark, "styleUrl")
        path_style_url.text = "#flightPath"
          # LineString for the path
        linestring = ET.SubElement(path_placemark, "LineString")
        extrude = ET.SubElement(linestring, "extrude")
        extrude.text = "0"  # Don't extend to ground
        tessellate = ET.SubElement(linestring, "tessellate")
        tessellate.text = "0"  # Don't follow terrain
        altitude_mode = ET.SubElement(linestring, "altitudeMode")
        altitude_mode.text = "absolute"
        
        # Coordinates
        coordinates = ET.SubElement(linestring, "coordinates")
        coord_string = ""
        
        for _, row in df.iterrows():
            # KML format: longitude,latitude,altitude
            coord_string += f"{row['lng']},{row['lat']},{row['alt']}\n"
        
        coordinates.text = coord_string.strip()
        
        # Create the main first-person tour
        self._create_fpv_tour(df, flight_name)
        
    def _create_fpv_tour(self, df, flight_name):
        """Create a comprehensive first-person view tour"""
        # Reduce data points for smooth tour (every 5th point for responsive playback)
        step = max(1, len(df) // 200)  # Limit to ~200 tour points max
        tour_df = df.iloc[::step].copy()
        
        console.print(f"🎬 [blue]Creating FPV tour with {len(tour_df)} camera positions[/blue]")
        
        tour = ET.SubElement(self.document, "gx:Tour")
        
        tour_name = ET.SubElement(tour, "name")
        tour_name.text = f"🚁 {flight_name} - First Person View"
        
        tour_description = ET.SubElement(tour, "description")
        tour_description.text = """🎮 DRONE FIRST PERSON VIEW EXPERIENCE 🎮
        
This tour puts you in the pilot's seat! 

🎯 CONTROLS:
• Click PLAY to start the FPV experience
• Use + / - to adjust playback speed
• Click the tour name to restart

📈 FEATURES:
• Real drone attitude (pitch, roll, yaw)
• Actual GPS coordinates and altitude
• Smooth camera transitions
• Immersive flight perspective

🚁 Enjoy the flight!"""
        
        playlist = ET.SubElement(tour, "gx:Playlist")
        
        # Calculate smooth transitions
        for i, (_, row) in enumerate(tour_df.iterrows()):
            
            # Calculate camera position (slightly behind and above drone for better view)
            heading = row['yaw'] if not pd.isna(row['yaw']) else 0
            pitch_angle = row['pitch'] if not pd.isna(row['pitch']) else 0
            roll_angle = row['roll'] if not pd.isna(row['roll']) else 0
            
            # Normalize heading to 0-360
            heading = heading % 360
            
            # Calculate camera tilt based on pitch (FPV perspective)
            # Pitch down = look down (positive tilt), Pitch up = look up (negative tilt)
            camera_tilt = 90 + pitch_angle  # Convert pitch to Google Earth tilt
            camera_tilt = max(0, min(180, camera_tilt))  # Clamp to valid range
            
            # Camera position: slightly offset from drone position for better perspective
            offset_distance = 2.0  # 2 meters behind the drone
            
            # Calculate offset position in lat/lng
            heading_rad = math.radians(heading)
            
            # Rough conversion (approximate for small distances)
            lat_offset = -offset_distance * math.cos(heading_rad) / 111320.0  # 1 degree lat ≈ 111320m
            lng_offset = -offset_distance * math.sin(heading_rad) / (111320.0 * math.cos(math.radians(row['lat'])))
            
            camera_lat = row['lat'] + lat_offset
            camera_lng = row['lng'] + lng_offset
            camera_alt = row['alt'] + 1.5  # Slightly above drone
            
            # FlyTo element
            flyto = ET.SubElement(playlist, "gx:FlyTo")
            
            # Shorter duration for smooth motion
            duration = ET.SubElement(flyto, "gx:duration")
            if i == 0:
                duration.text = "3.0"  # Longer for first position
            else:
                duration.text = "0.8"  # Fast transitions for smooth FPV
            
            flyto_mode = ET.SubElement(flyto, "gx:flyToMode")
            flyto_mode.text = "smooth"
            
            # Camera element for first-person perspective
            camera = ET.SubElement(flyto, "Camera")
            
            longitude = ET.SubElement(camera, "longitude")
            longitude.text = str(camera_lng)
            
            latitude = ET.SubElement(camera, "latitude")
            latitude.text = str(camera_lat)
            
            altitude = ET.SubElement(camera, "altitude")
            altitude.text = str(camera_alt)
            
            camera_heading = ET.SubElement(camera, "heading")
            camera_heading.text = str(heading)
            
            camera_tilt_elem = ET.SubElement(camera, "tilt")
            camera_tilt_elem.text = str(camera_tilt)
            
            camera_roll = ET.SubElement(camera, "roll")
            camera_roll.text = str(-roll_angle)  # Negative for correct roll direction
            
            camera_altitude_mode = ET.SubElement(camera, "altitudeMode")
            camera_altitude_mode.text = "absolute"
            
            # Add wait between some positions for dramatic effect
            if i % 20 == 0 and i > 0:  # Every 20th position
                wait = ET.SubElement(playlist, "gx:Wait")
                wait_duration = ET.SubElement(wait, "gx:duration")
                wait_duration.text = "0.5"    
    def save_kml(self, output_path):
        """Save the KML to file"""
        if self.kml_root is None:
            console.print("❌ [red]No KML data to save[/red]")
            return
            
        # Pretty print the XML
        rough_string = ET.tostring(self.kml_root, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        pretty_xml = reparsed.toprettyxml(indent="  ")
        
        # Remove empty lines
        pretty_xml = '\n'.join([line for line in pretty_xml.split('\n') if line.strip()])
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(pretty_xml)
        
        console.print(f"✔️ [green]KML saved to {output_path}[/green]")

def process_bin_files():
    """Main function to process all BIN files and generate FPV KML"""
    console.print("🚁 [bold cyan]DRONE FIRST-PERSON VIEW KML GENERATOR[/bold cyan]")
    console.print("=" * 60)
    console.print("🎮 [yellow]Creating immersive FPV experience for Google Earth[/yellow]")
    console.print("=" * 60)
    
    # Directories
    bin_dir = "./logs/bin"
    kml_dir = "./logs/kml"
    
    # Create KML output directory
    os.makedirs(kml_dir, exist_ok=True)
    
    if not os.path.exists(bin_dir):
        console.print(f"❌ [red]BIN directory not found: {bin_dir}[/red]")
        return
    
    # Get all BIN files
    bin_files = [f for f in os.listdir(bin_dir) if f.endswith('.bin')]
    
    if not bin_files:
        console.print(f"❌ [red]No BIN files found in {bin_dir}[/red]")
        return
    
    console.print(f"📁 [blue]Found {len(bin_files)} BIN files to process[/blue]")
    
    # Process each BIN file
    for bin_file in bin_files:
        console.print(f"\n🔄 [yellow]Processing: {bin_file}[/yellow]")
        
        bin_path = os.path.join(bin_dir, bin_file)
        flight_name = os.path.splitext(bin_file)[0]
        kml_path = os.path.join(kml_dir, f"FPV_{flight_name}.kml")
        
        try:
            # Create KML generator
            kml_gen = DroneKMLGenerator()
            kml_gen.create_kml_structure(flight_name)
            
            # Parse BIN file
            flight_data = kml_gen.parse_flight_data(bin_path)
            
            if flight_data is not None and not flight_data.empty:
                # Create flight path and FPV tour
                kml_gen.create_flight_path(flight_data, flight_name)
                
                # Save KML
                kml_gen.save_kml(kml_path)
                
                # Display comprehensive statistics
                stats_table = Table(title=f"🚁 Flight Analysis - {flight_name}", show_header=True)
                stats_table.add_column("📊 Metric", style="cyan", width=20)
                stats_table.add_column("📈 Value", style="green", width=25)
                
                # Calculate additional stats
                duration = flight_data['timestamp'].max() - flight_data['timestamp'].min()
                distance_2d = 0
                for i in range(1, len(flight_data)):
                    prev_row = flight_data.iloc[i-1]
                    curr_row = flight_data.iloc[i]
                    # Rough 2D distance calculation
                    lat_diff = (curr_row['lat'] - prev_row['lat']) * 111320  # meters per degree lat
                    lng_diff = (curr_row['lng'] - prev_row['lng']) * 111320 * math.cos(math.radians(curr_row['lat']))
                    distance_2d += math.sqrt(lat_diff**2 + lng_diff**2)
                
                stats_table.add_row("🎯 Total GPS Points", str(len(flight_data)))
                stats_table.add_row("⏱️ Flight Duration", f"{duration:.1f} seconds")
                stats_table.add_row("📏 Distance Traveled", f"{distance_2d:.1f} meters")
                stats_table.add_row("⛰️ Max Altitude", f"{flight_data['alt'].max():.1f} m")
                stats_table.add_row("🌊 Min Altitude", f"{flight_data['alt'].min():.1f} m")
                stats_table.add_row("📡 Altitude Range", f"{flight_data['alt'].max() - flight_data['alt'].min():.1f} m")
                stats_table.add_row("🌍 Lat Range", f"{flight_data['lat'].min():.6f} to {flight_data['lat'].max():.6f}")
                stats_table.add_row("🌍 Lng Range", f"{flight_data['lng'].min():.6f} to {flight_data['lng'].max():.6f}")
                stats_table.add_row("🎮 FPV Camera Points", str(len(flight_data[::max(1, len(flight_data) // 200)])))
                
                # Attitude statistics
                if 'roll' in flight_data.columns:
                    stats_table.add_row("🎲 Max Roll", f"{flight_data['roll'].max():.1f}°")
                    stats_table.add_row("📐 Max Pitch", f"{flight_data['pitch'].max():.1f}°")
                    stats_table.add_row("🧭 Yaw Range", f"{flight_data['yaw'].min():.1f}° to {flight_data['yaw'].max():.1f}°")
                
                console.print(stats_table)
                
            else:
                console.print(f"⚠️ [yellow]No valid flight data found in {bin_file}[/yellow]")
                
        except Exception as e:
            console.print(f"❌ [red]Error processing {bin_file}: {str(e)}[/red]")
            import traceback
            console.print(f"[red]{traceback.format_exc()}[/red]")
    
    console.print(f"\n🎉 [bold green]FPV KML files generated in {kml_dir}[/bold green]")
    console.print("\n" + "=" * 60)
    console.print("🎮 [bold cyan]HOW TO EXPERIENCE THE FIRST-PERSON VIEW:[/bold cyan]")
    console.print("=" * 60)
    console.print("1. 📂 Open Google Earth Pro (desktop version)")
    console.print("2. 📁 File > Open > Select a FPV_*.kml file")
    console.print("3. 🎬 In the 'Places' panel, find the tour (🚁 icon)")
    console.print("4. ▶️ Click the PLAY button to start FPV experience")
    console.print("5. 🎮 Use +/- to adjust playback speed")
    console.print("6. 🔄 Click tour name to restart from beginning")
    console.print("\n🚁 [yellow]You'll experience the flight from the drone's perspective!")
    console.print("🎯 [yellow]Camera follows actual GPS coordinates and drone attitude!")
    console.print("=" * 60)

if __name__ == "__main__":
    process_bin_files()