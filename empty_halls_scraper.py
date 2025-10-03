"""
Empty Halls Finder for FSHN - Debug Version
"""

from flask import Flask, render_template_string, jsonify, request
from bs4 import BeautifulSoup
import requests
from datetime import datetime
from collections import defaultdict
import json

app = Flask(__name__)

# IMPORTANT: Update this with your actual URL
BASE_URL = "http://37.139.119.36:81/orari/student"

class ScheduleScraper:
    def scrape_all(self):
        """Scrape all departments, years, and groups and aggregate hall usage"""
        self.log("\n=== Scraping all schedules for faculty ===")
        departments = self.get_departments()
        if not departments:
            self.log("No departments found!")
            return False
        for dept in departments:
            dept_val = dept['value']
            dept_name = dept['name']
            self.log(f"Department: {dept_name}")
            # Get years for department
            try:
                years_resp = requests.get(f"{self.base_url}/getYear/{dept_val}", timeout=10)
                years_soup = BeautifulSoup(years_resp.content, 'html.parser')
                years = [opt.get('value') for opt in years_soup.find_all('option') if opt.get('value') and opt.get('value') != '0']
            except Exception as e:
                self.log(f"  Error fetching years: {e}")
                continue
            for year in years:
                # Get groups for department/year
                try:
                    groups_resp = requests.get(f"{self.base_url}/getGroup/{dept_val}/{year}", timeout=10)
                    groups_soup = BeautifulSoup(groups_resp.content, 'html.parser')
                    groups = [opt.get('value') for opt in groups_soup.find_all('option') if opt.get('value') and opt.get('value') != '0']
                except Exception as e:
                    self.log(f"    Error fetching groups: {e}")
                    continue
                for group in groups:
                    self.log(f"  Scraping: {dept_name} - {year} - {group}")
                    self.scrape_schedule_simple(dept_val, year, group)
        self.log(f"\nFaculty scraping complete! Found {len(self.halls)} unique halls.")
        return True
    def __init__(self, base_url):
        self.base_url = base_url
        self.schedule_data = defaultdict(lambda: defaultdict(list))
        self.halls = set()
        self.debug_info = []
        
    def log(self, message):
        print(message)
        self.debug_info.append(message)
    
    def test_connection(self):
        """Test if we can connect to the website"""
        try:
            self.log(f"Testing connection to {self.base_url}/student")
            response = requests.get(f"{self.base_url}/student", timeout=10)
            self.log(f"Status code: {response.status_code}")
            
            if response.status_code == 200:
                self.log("✓ Connection successful!")
                # Save HTML for inspection
                with open('test_page.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                self.log("Saved page to test_page.html for inspection")
                return True
            else:
                self.log(f"✗ Connection failed with status {response.status_code}")
                return False
        except Exception as e:
            self.log(f"✗ Connection error: {str(e)}")
            return False
    
    def get_departments(self):
        """Scrape list of all departments"""
        try:
            self.log("\n=== Fetching Departments ===")
            response = requests.get(f"{self.base_url}/student", timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            dept_select = soup.find('select', {'id': 'ddlDega'})
            departments = []
            
            if dept_select:
                for option in dept_select.find_all('option'):
                    value = option.get('value', '')
                    if value and value != '0':
                        departments.append({
                            'value': value,
                            'name': option.text.strip()
                        })
                
                self.log(f"Found {len(departments)} departments")
                for dept in departments[:3]:  # Show first 3
                    self.log(f"  - {dept['name']}")
                if len(departments) > 3:
                    self.log(f"  ... and {len(departments) - 3} more")
            else:
                self.log("✗ Could not find department dropdown")
            
            return departments
        except Exception as e:
            self.log(f"✗ Error fetching departments: {e}")
            return []
    
    def scrape_schedule_simple(self, department, year, group):
        """Simple version - scrape one schedule and show what we find"""
        try:
            self.log(f"\n=== Scraping Schedule ===")
            self.log(f"Department: {department}")
            self.log(f"Year: {year}")
            self.log(f"Group: {group}")
            
            # POST request to get schedule
            data = {
                'dega': department,
                'viti': year,
                'paraleli': group,
                'submit': 'Afisho'
            }
            
            response = requests.post(f"{self.base_url}/student", data=data, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Save this schedule for inspection
            with open('schedule_test.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            self.log("Saved schedule to schedule_test.html")
            
            # Find the schedule table
            table = soup.find('table', {'class': 'contentTextFormat'})
            if not table:
                self.log("✗ Could not find schedule table")
                return False
            
            self.log("✓ Found schedule table")
            
            # Parse the table structure
            days = ['E Hënë', 'E Martë', 'E Mërkurë', 'E Enjte', 'E Premte']
            rows = table.find_all('tr')
            
            self.log(f"Table has {len(rows)} rows")
            
            # Skip first 2 rows (headers)
            for row_idx, row in enumerate(rows[2:], start=0):
                th = row.find('th')
                if not th:
                    continue
                    
                time_slot = th.text.strip()
                cells = row.find_all('td', {'class': 'bodyTd'})
                
                for day_idx, cell in enumerate(cells):
                    if day_idx >= len(days):
                        break
                    
                    cell_text = cell.text.strip()
                    
                    # Skip empty cells
                    if not cell_text or cell_text == '&nbsp' or cell_text == '':
                        continue
                    
                    self.log(f"\nFound class:")
                    self.log(f"  Time: {time_slot}")
                    self.log(f"  Day: {days[day_idx]}")
                    self.log(f"  Content: {cell_text[:100]}...")  # First 100 chars
                    
                    # Try to extract hall information using regex (look for Salla or Klasa)
                    import re
                    lines = [line.strip() for line in cell_text.split('\n') if line.strip()]
                    hall = None
                    for line in reversed(lines):
                        match = re.search(r'(Salla|Klasa)\s*\(?([\w\d\-]+)\)?', line, re.IGNORECASE)
                        if match:
                            hall = match.group(0).strip()
                            # Clean up hall name (remove extra spaces, normalize)
                            hall = re.sub(r'\s+', ' ', hall)
                            break
                    if hall:
                        self.log(f"  Hall detected: {hall}")
                        self.halls.add(hall)
                        # Store schedule entry
                        day = days[day_idx]
                        if '-' in time_slot:
                            start_time, end_time = time_slot.split('-')
                            self.schedule_data[day][hall].append({
                                'start': start_time.strip(),
                                'end': end_time.strip(),
                                'subject': lines[0] if lines else "Unknown",
                                'professor': lines[1] if len(lines) > 1 else "Unknown",
                                'group': f"{year} - {group}"
                            })
            
            self.log(f"\n✓ Scraping complete! Found {len(self.halls)} unique halls")
            for hall in list(self.halls)[:5]:
                self.log(f"  - {hall}")
            
            return True
            
        except Exception as e:
            self.log(f"✗ Error scraping schedule: {e}")
            import traceback
            self.log(traceback.format_exc())
            return False



# HTML Template for students (no debug, no scrape, auto-update)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang=\"sq\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>Sallat e Lira | FSHN</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        .main-content { background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px 8px 0 0; }
        .header h1 { font-size: 28px; margin-bottom: 10px; }
        .controls { padding: 25px; background: #f8f9fa; border-bottom: 1px solid #e0e0e0; }
        .control-row { display: flex; gap: 15px; flex-wrap: wrap; align-items: center; margin-bottom: 15px; }
        select, input, button { padding: 10px 15px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px; }
        button { background: #667eea; color: white; border: none; cursor: pointer; font-weight: 600; }
        button:hover { background: #5568d3; }
        .current-time { background: #e3f2fd; padding: 15px 25px; display: flex; justify-content: space-between; }
        .time-display { font-size: 18px; font-weight: bold; color: #1565c0; }
        .summary { background: #f8f9fa; padding: 20px; margin: 20px; border-radius: 8px; display: flex; justify-content: space-around; text-align: center; }
        .summary-number { font-size: 32px; font-weight: bold; color: #667eea; }
        .summary-label { color: #666; margin-top: 5px; }
        .hall-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 20px; padding: 25px; }
        .hall-card { border: 2px solid #e0e0e0; border-radius: 8px; padding: 20px; transition: all 0.3s; }
        .hall-card.free { background: #e8f5e9; border-color: #4caf50; }
        .hall-card.occupied { background: #ffebee; border-color: #f44336; }
        .hall-card:hover { transform: translateY(-3px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
        .hall-name { font-size: 20px; font-weight: bold; margin-bottom: 10px; }
        .hall-status { display: inline-block; padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; margin-bottom: 10px; }
        .status-free { background: #4caf50; color: white; }
        .status-occupied { background: #f44336; color: white; }
        .class-info { margin-top: 10px; padding: 8px; background: #fff3e0; border-left: 3px solid #ff9800; font-size: 12px; }
        .alert { padding: 15px; margin: 20px; border-radius: 5px; }
        .alert-info { background: #e3f2fd; border-left: 4px solid #2196f3; }
        .alert-warning { background: #fff3e0; border-left: 4px solid #ff9800; }
        .alert-danger { background: #ffebee; border-left: 4px solid #f44336; }
        .loading { text-align: center; padding: 40px; }
        .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #667eea; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 20px auto; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class=\"container\">
        <div class=\"main-content\">
            <div class=\"header\">
                <h1>🏛️ Sallat e Lira</h1>
                <p>Fakulteti i Shkencave të Natyrës</p>
            </div>
            <div class=\"current-time\">
                <span>📅 Koha aktuale:</span>
                <span class=\"time-display\" id=\"currentTime\"></span>
            </div>
            <div class=\"controls\">
                <h3 style=\"margin-bottom: 15px;\">🔍 Gjej Sallat e Lira</h3>
                <div class=\"control-row\">
                    <select id=\"daySelect\">
                        <option value=\"E Hënë\">E Hënë</option>
                        <option value=\"E Martë\">E Martë</option>
                        <option value=\"E Mërkurë\">E Mërkurë</option>
                        <option value=\"E Enjte\">E Enjte</option>
                        <option value=\"E Premte\">E Premte</option>
                    </select>
                    <input type=\"time\" id=\"timeSelect\" value=\"09:00\">
                    <button onclick=\"useCurrentTime()\">⏰ Tani</button>
                </div>
            </div>
            <div id=\"alerts\"></div>
            <div id=\"results\" style=\"display:none;\;\">
                <div class=\"summary\">
                    <div>
                        <div class=\"summary-number\" id=\"totalHalls\">0</div>
                        <div class=\"summary-label\">Total Salla</div>
                    </div>
                    <div>
                        <div class=\"summary-number\" id=\"freeHalls\" style=\"color: #4caf50;\">0</div>
                        <div class=\"summary-label\">Salla të Lira</div>
                    </div>
                    <div style=\"display:none;\">
                        <div class=\"summary-number\" id=\"occupiedHalls\" style=\"color: #f44336;\">0</div>
                        <div class=\"summary-label\">Salla të Zëna</div>
                    </div>
                </div>
                <div class=\"hall-grid\" id=\"hallGrid\"></div>
            </div>
        </div>
        <div id=\"loading\" class=\"loading\" style=\"display:none;\"><div class=\"spinner\"></div>Po ngarkohen të dhënat...</div>
    </div>
    <script>
        let scheduleData = {};
        let hallsList = [];

        function showAlert(message, type = 'info') {
            const alerts = document.getElementById('alerts');
            const alert = document.createElement('div');
            alert.className = `alert alert-${type}`;
            alert.textContent = message;
            alerts.appendChild(alert);
            setTimeout(() => alert.remove(), 5000);
        }

        function updateCurrentTime() {
            const now = new Date();
            const days = ["E Diel", "E Hënë", "E Martë", "E Mërkurë", "E Enjte", "E Premte", "E Shtunë"];
            const day = days[now.getDay()];
            const time = now.toLocaleTimeString('sq-AL', { hour: '2-digit', minute: '2-digit' });
            document.getElementById('currentTime').textContent = day + ', ' + time;
        }

        window.addEventListener('DOMContentLoaded', function() {
            updateCurrentTime();
            setInterval(updateCurrentTime, 1000);
            // Set day select to today if weekday
            const now = new Date();
            const days = ["E Diel", "E Hënë", "E Martë", "E Mërkurë", "E Enjte", "E Premte", "E Shtunë"];
            const day = days[now.getDay()];
            if (now.getDay() >= 1 && now.getDay() <= 5) {
                document.getElementById('daySelect').value = day;
            } else {
                document.getElementById('daySelect').value = "E Hënë";
            }
            // Fetch schedule data
            fetchSchedule();
            // Add listeners for auto-update
            document.getElementById('daySelect').addEventListener('change', findEmptyHalls);
            document.getElementById('timeSelect').addEventListener('input', findEmptyHalls);
        });

        function useCurrentTime() {
            const now = new Date();
            const time = now.toTimeString().slice(0, 5);
            document.getElementById('timeSelect').value = time;
            findEmptyHalls();
        }

        function timeToMinutes(time) {
            const [hours, minutes] = time.split(':').map(Number);
            return hours * 60 + minutes;
        }

        function isHallOccupied(hall, day, time) {
            if (!scheduleData[day] || !scheduleData[day][hall]) return null;
            const timeMinutes = timeToMinutes(time);
            for (const cls of scheduleData[day][hall]) {
                const startMinutes = timeToMinutes(cls.start);
                const endMinutes = timeToMinutes(cls.end);
                if (timeMinutes >= startMinutes && timeMinutes < endMinutes) {
                    return cls;
                }
            }
            return null;
        }

        function findEmptyHalls() {
            if (hallsList.length === 0) {
                document.getElementById('results').style.display = 'none';
                document.getElementById('alerts').innerHTML = '';
                showAlert('Nuk ka të dhëna të orarit të publikuara. Ju lutem kontaktoni administratën.', 'warning');
                return;
            }
            const day = document.getElementById('daySelect').value;
            const time = document.getElementById('timeSelect').value;
            const grid = document.getElementById('hallGrid');
            grid.innerHTML = '';
            document.getElementById('results').style.display = 'block';
            let freeCount = 0;
            hallsList.forEach(hall => {
                const currentClass = isHallOccupied(hall, day, time);
                if (!currentClass) {
                    freeCount++;
                    const card = document.createElement('div');
                    card.className = 'hall-card free';
                    let content = '<div class="hall-name">' + hall + '</div>';
                    content += '<span class="hall-status status-free">✓ E Lirë</span>';
                    card.innerHTML = content;
                    grid.appendChild(card);
                }
            });
            document.getElementById('totalHalls').textContent = hallsList.length;
            document.getElementById('freeHalls').textContent = freeCount;
            // Hide occupied halls summary if present
            var occ = document.getElementById('occupiedHalls');
            if (occ && occ.parentElement) occ.parentElement.style.display = 'none';
        }

        function fetchSchedule() {
            document.getElementById('loading').style.display = 'block';
            fetch('/api/schedule').then(r => r.json()).then(data => {
                scheduleData = data.schedule || {};
                hallsList = data.halls || [];
                document.getElementById('loading').style.display = 'none';
                findEmptyHalls();
            }).catch(() => {
                document.getElementById('loading').style.display = 'none';
                showAlert('Gabim gjatë ngarkimit të të dhënave.', 'danger');
            });
        }
    </script>
</body>
</html>
"""



# Global cache for all halls and schedule

import os
from functools import wraps
from flask import Response

CACHE_FILE = 'schedule_cache.json'
faculty_scraper = None
faculty_schedule = {}
faculty_halls = []
faculty_debug = []

def load_cache():
    global faculty_schedule, faculty_halls, faculty_debug
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            faculty_schedule = data.get('schedule', {})
            faculty_halls = data.get('halls', [])
            faculty_debug = data.get('debug', [])
            print('Loaded schedule cache.')
    else:
        print('No cache file found.')

def save_cache():
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            'schedule': faculty_schedule,
            'halls': faculty_halls,
            'debug': faculty_debug
        }, f, ensure_ascii=False, indent=2)
        print('Saved schedule cache.')

load_cache()

ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'admin123')

# === Scheduled scraping (once a day at 00:00 Berlin time) ===
# --- Admin authentication decorator ---
def check_auth(username, password):
    return username == ADMIN_USER and password == ADMIN_PASS

def authenticate():
    return Response(
        'Admin access required.\n', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    import pytz
    def scheduled_refresh():
        global faculty_scraper, faculty_schedule, faculty_halls, faculty_debug
        print("[SCHEDULED] Refreshing faculty schedule cache...")
        faculty_scraper = ScheduleScraper(BASE_URL)
        success = faculty_scraper.scrape_all()
        if success:
            faculty_schedule = dict(faculty_scraper.schedule_data)
            faculty_halls = list(faculty_scraper.halls)
            faculty_debug = faculty_scraper.debug_info
            save_cache()
            print("[SCHEDULED] Faculty schedule cache refreshed.")
        else:
            print("[SCHEDULED] Faculty schedule refresh failed.")
    scheduler = BackgroundScheduler(timezone=pytz.timezone('Europe/Berlin'))
    scheduler.add_job(scheduled_refresh, 'cron', hour=0, minute=0)
    scheduler.start()
except ImportError:
    print("APScheduler or pytz not installed. Scheduled scraping is disabled.")


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


# Admin-only: refresh schedule and update cache (protected by HTTP Basic Auth)
@app.route('/api/refresh-schedule', methods=['POST'])
@requires_auth
def refresh_schedule():
    global faculty_scraper, faculty_schedule, faculty_halls, faculty_debug
    faculty_scraper = ScheduleScraper(BASE_URL)
    success = faculty_scraper.scrape_all()
    faculty_schedule = dict(faculty_scraper.schedule_data)
    faculty_halls = list(faculty_scraper.halls)
    faculty_debug = faculty_scraper.debug_info
    save_cache()
    return jsonify({
        'success': success,
        'schedule': faculty_schedule,
        'halls': faculty_halls,
        'debug': faculty_debug
    })

@app.route('/api/schedule')
def get_schedule():
    global faculty_schedule, faculty_halls, faculty_debug
    # Always serve from cache
    return jsonify({
        'schedule': faculty_schedule,
        'halls': faculty_halls
    })

if __name__ == '__main__':
    print("=" * 60)
    print("Empty Halls Finder - Student Mode")
    print("=" * 60)
    print(f"\nBase URL: {BASE_URL}")
    print("\nIMPORTANT: Make sure BASE_URL is correct!")
    print("\nStarting server on http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)