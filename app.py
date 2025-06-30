from flask import Flask, render_template, jsonify, request
from traceroute import traceroute, get_ip_location
import folium
from folium import plugins
import json
import requests

app = Flask(__name__)

# Helper to get server public IP geolocation

def get_server_location():
    try:
        ip = requests.get('https://api.ipify.org').text
        loc = get_ip_location(ip)
        return loc
    except:
        return {'city': '', 'country': '', 'latitude': 0, 'longitude': 0}

@app.route('/')
def index():
    # Create a base map centered on the world
    m = folium.Map(
        location=[20, 0],
        zoom_start=2,
        tiles='CartoDB dark_matter'
    )
    return render_template('index.html', map=m._repr_html_())

@app.route('/trace', methods=['POST'])
def trace():
    data = request.json
    target = data.get('target')
    user_location = data.get('user_location')
    print('Received user_location:', user_location)
    if not target:
        return jsonify({'error': 'No target specified'}), 400

    try:
        hops = traceroute(target)
        # Get fallback location (server public IP)
        server_loc = get_server_location()
        # Patch hops: for private, use user_location if present, else server_loc
        for hop in hops:
            if hop.location and hop.location['latitude'] == 0 and hop.location['longitude'] == 0:
                hop.is_private = True
                if user_location and 'latitude' in user_location and 'longitude' in user_location:
                    hop.location['latitude'] = user_location['latitude']
                    hop.location['longitude'] = user_location['longitude']
                    print('Set private hop location to user_location:', hop.location)
                else:
                    hop.location['latitude'] = server_loc['latitude']
                    hop.location['longitude'] = server_loc['longitude']
                    print('Set private hop location to server_loc:', hop.location)
            else:
                hop.is_private = False
            print(f'Hop {hop.ip} final location:', hop.location)
        
        # Create map
        m = folium.Map(
            location=[20, 0],
            zoom_start=2,
            tiles='CartoDB dark_matter'
        )

        # Create feature group for lines
        lines = folium.FeatureGroup(name="Lines")
        
        # Create markers and lines
        coordinates = []
        for i, hop in enumerate(hops):
            if hop.location and 'latitude' in hop.location and 'longitude' in hop.location:
                lat, lon = hop.location['latitude'], hop.location['longitude']
                coordinates.append([lat, lon])
                
                # Add marker
                popup_text = f"""
                Hop {i+1}<br>
                IP: {hop.ip}<br>
                Hostname: {hop.hostname}<br>
                RTT: {hop.rtt:.2f}ms<br>
                Location: {hop.location.get('city', 'Unknown')}, {hop.location.get('country', 'Unknown')}
                """
                
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=8,
                    popup=popup_text,
                    color='#FF0000',
                    fill=True,
                    fillColor='#FF0000'
                ).add_to(m)

        # Add lines connecting the points
        if len(coordinates) > 1:
            folium.PolyLine(
                coordinates,
                weight=2,
                color='red',
                opacity=0.8
            ).add_to(m)

        # Add animated markers
        plugins.AntPath(coordinates).add_to(m)

        return jsonify({
            'map': m._repr_html_(),
            'hops': [
                {
                    'ip': hop.ip,
                    'hostname': hop.hostname,
                    'rtt': round(hop.rtt, 2),
                    'location': hop.location,
                    'is_private': getattr(hop, 'is_private', False)
                }
                for hop in hops
            ]
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 