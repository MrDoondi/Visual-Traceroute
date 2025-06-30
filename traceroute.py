import socket
import subprocess
import sys
import re
from geolite2 import geolite2
import requests
from typing import List, Dict, Optional
import time
import ipaddress
import shutil

class TracerouteHop:
    def __init__(self, ip: str, rtt: float = 0.0, location: Dict = None):
        self.ip = ip
        self.rtt = rtt
        self.location = location or {}
        self.hostname = None
        try:
            self.hostname = socket.gethostbyaddr(ip)[0]
        except:
            self.hostname = ip

def get_ip_location(ip: str) -> Optional[Dict]:
    # Check for private IPs
    try:
        if ipaddress.ip_address(ip).is_private:
            return {
                'city': '',
                'country': '',
                'latitude': 0,
                'longitude': 0
            }
    except Exception:
        pass
    try:
        # First try to use MaxMind GeoLite2 database
        reader = geolite2.reader()
        location = reader.get(ip)
        if location:
            return {
                'city': location.get('city', {}).get('names', {}).get('en', 'Unknown'),
                'country': location.get('country', {}).get('names', {}).get('en', 'Unknown'),
                'latitude': location.get('location', {}).get('latitude', 0),
                'longitude': location.get('location', {}).get('longitude', 0)
            }
    except:
        # Fallback to ip-api.com (free tier)
        try:
            response = requests.get(f'http://ip-api.com/json/{ip}', timeout=2)
            if response.status_code == 200:
                data = response.json()
                return {
                    'city': data.get('city', 'Unknown'),
                    'country': data.get('country', 'Unknown'),
                    'latitude': data.get('lat', 0),
                    'longitude': data.get('lon', 0)
                }
        except:
            pass
    return {
        'city': '',
        'country': '',
        'latitude': 0,
        'longitude': 0
    }

def is_valid_ip(ip: str) -> bool:
    try:
        socket.inet_pton(socket.AF_INET, ip)
        return True
    except OSError:
        try:
            socket.inet_pton(socket.AF_INET6, ip)
            return True
        except OSError:
            return False

def traceroute(target: str, max_hops: int = 30, timeout: int = 2) -> List[TracerouteHop]:
    """
    Perform a traceroute using the system command and return a list of hops with their locations
    """
    hops = []
    traceroute_path = shutil.which('traceroute')
    tracepath_path = shutil.which('tracepath')
    print('Traceroute path:', traceroute_path)
    print('Tracepath path:', tracepath_path)
    if sys.platform.startswith('win'):
        cmd = ["tracert", "-d", "-h", str(max_hops), target]
    else:
        if traceroute_path:
            cmd = [traceroute_path, "-n", "-m", str(max_hops), target]
        elif tracepath_path:
            cmd = [tracepath_path, target]
        else:
            raise RuntimeError("Neither traceroute nor tracepath is available on this system.")
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output, _ = proc.communicate(timeout=60)
    except Exception as e:
        raise RuntimeError(f"Traceroute failed: {e}")

    for line in output.splitlines():
        print(f"Parsing line: {line}")  # Debug print
        if sys.platform.startswith('win'):
            if 'Request timed out' in line or line.strip() == '' or line.startswith('Tracing') or line.startswith('over a maximum') or line.startswith('Trace complete'):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            ip_candidate = parts[-1]
            if is_valid_ip(ip_candidate):
                print(f"Found hop IP: {ip_candidate}")  # Debug print
                location = get_ip_location(ip_candidate)
                hop = TracerouteHop(ip_candidate, 0.0, location)
                hops.append(hop)
        else:
            # Accept both IPv4 and IPv6 addresses
            m = re.match(r"\s*(\d+)\s+([\da-fA-F\.:]+)(.*)", line)
            if m:
                ip = m.group(2)
                if is_valid_ip(ip):
                    print(f"Found hop IP: {ip}")  # Debug print
                    location = get_ip_location(ip)
                    hop = TracerouteHop(ip, 0.0, location)
                    hops.append(hop)
            # tracepath output:  1?: [LOCALHOST]                      pmtu 1500
            #                   1:  192.168.1.1  0.463ms
            #                   2:  8.8.8.8      10.123ms reached
            if tracepath_path:
                m2 = re.match(r"\s*\d+:\s+([\da-fA-F\.:]+)\s+", line)
                if m2:
                    ip = m2.group(1)
                    if is_valid_ip(ip):
                        print(f"Found hop IP (tracepath): {ip}")  # Debug print
                        location = get_ip_location(ip)
                        hop = TracerouteHop(ip, 0.0, location)
                        hops.append(hop)
    return hops 