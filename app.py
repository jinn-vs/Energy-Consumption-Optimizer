from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
import requests
import json
from datetime import date, timedelta
from config import MYSQL_PASSWORD, WEATHER_API_KEY

app = Flask(__name__)
app.secret_key = 'energy_optimizer_secret_123'

# -------- DATABASE CONNECTION --------
def get_db():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password=MYSQL_PASSWORD,
        database='energy_optimizer'
    )

# -------- WEATHER API --------
WEATHER_API_KEY = WEATHER_API_KEY

def get_weather(city='Rawalpindi'):
    try:
        url = f'http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={WEATHER_API_KEY}&units=metric'
        response = requests.get(url, timeout=5)
        data = response.json()
        if data.get('cod') == '200':
            current = data['list'][0]
            weather = {
                'temp': current['main']['temp'],
                'description': current['weather'][0]['description'],
                'clouds': current['clouds']['all'],
                'humidity': current['main']['humidity'],
                'icon': current['weather'][0]['icon']
            }
            return weather
    except:
        pass
    return {'temp': 35, 'description': 'clear sky', 'clouds': 10, 'humidity': 40, 'icon': '01d'}

def get_solar_factor(clouds, rain=False):
    if rain:
        return 0.15
    elif clouds < 20:
        return 0.95
    elif clouds < 50:
        return 0.70
    elif clouds < 80:
        return 0.40
    else:
        return 0.20

# -------- HOME PAGE --------
@app.route('/')
def home():
    return render_template('home.html')

# -------- REGISTER --------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        city = request.form.get('city', 'Rawalpindi')
        solar = 1 if request.form.get('solar_panels') else 0
        panel_count = int(request.form.get('panel_count', 0))
        panel_wattage = int(request.form.get('panel_wattage', 0))
        monthly_budget_rs = float(request.form.get('monthly_budget_rs', 5000))
        per_unit_cost = float(request.form.get('per_unit_cost', 55))

        db = get_db()
        cursor = db.cursor(dictionary=True)
        try:
            cursor.execute(
                "INSERT INTO users (name, email, password, city, solar_panels, panel_count, panel_wattage, monthly_budget_rs, per_unit_cost) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (name, email, password, city, solar, panel_count, panel_wattage, monthly_budget_rs, per_unit_cost)
            )
            db.commit()
            flash('Account ban gaya! Ab login karo.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            flash('Yeh email pehle se registered hai.', 'danger')
        finally:
            cursor.close()
            db.close()

    return render_template('register.html')

# -------- LOGIN --------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['city'] = user['city']
            return redirect(url_for('dashboard'))
        else:
            flash('Ghalat email ya password!', 'danger')

    return render_template('login.html')

# -------- LOGOUT --------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# -------- DASHBOARD --------
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    city = session.get('city', 'Rawalpindi')
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Get user info
    cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()

    per_unit = user['per_unit_cost'] or 55
    monthly_budget_rs = user['monthly_budget_rs'] or 5000

    # Get appliances
    cursor.execute("SELECT * FROM appliances WHERE user_id=%s", (user_id,))
    appliances = cursor.fetchall()

    # Calculate daily consumption and cost
    total_daily_kwh = 0
    chart_labels = []
    chart_kwh = []
    chart_cost = []
    for a in appliances:
        daily = (a['wattage'] * a['avg_hours_per_day']) / 1000
        a['daily_kwh'] = round(daily, 2)
        a['daily_cost'] = round(daily * per_unit, 2)
        a['monthly_kwh'] = round(daily * 30, 2)
        a['monthly_cost'] = round(daily * 30 * per_unit, 2)
        total_daily_kwh += daily
        chart_labels.append(a['name'])
        chart_kwh.append(round(daily * 30, 2))
        chart_cost.append(round(daily * 30 * per_unit, 2))
    total_daily_kwh = round(total_daily_kwh, 2)

    # Monthly totals
    monthly_units = round(total_daily_kwh * 30, 2)
    monthly_cost = round(monthly_units * per_unit, 2)

    # Daily budget in kWh (derived from Rs budget)
    daily_budget_rs = round(monthly_budget_rs / 30, 2)
    daily_cost = round(total_daily_kwh * per_unit, 2)

    # Weather
    weather = get_weather(city)

    # Solar estimation
    solar_kwh = 0
    solar_savings = 0
    if user['solar_panels']:
        solar_factor = get_solar_factor(weather['clouds'], 'rain' in weather['description'].lower())
        peak_sun_hours = 5
        solar_kwh = round((user['panel_count'] * user['panel_wattage'] * peak_sun_hours * solar_factor) / 1000, 2)
        solar_savings = round(solar_kwh * 30 * per_unit, 2)

    # Net monthly cost after solar
    net_monthly_cost = round(monthly_cost - solar_savings, 2)

    # Budget warning
    budget_percent = round((net_monthly_cost / monthly_budget_rs) * 100, 2) if monthly_budget_rs > 0 else 0
    budget_warning = False
    budget_exceeded = False
    if budget_percent >= 100:
        budget_exceeded = True
    elif budget_percent >= 80:
        budget_warning = True

    # Margin bank
    daily_budget_kwh = round((monthly_budget_rs / per_unit) / 30, 2)
    banked = round(daily_budget_kwh - total_daily_kwh + solar_kwh, 2)

    # Today's log
    today = date.today().isoformat()
    cursor.execute("SELECT * FROM energy_logs WHERE user_id=%s AND log_date=%s", (user_id, today))
    today_log = cursor.fetchone()
    if not today_log:
        cursor.execute(
            "INSERT INTO energy_logs (user_id, log_date, total_kwh, solar_kwh, budget_kwh, banked_kwh) VALUES (%s,%s,%s,%s,%s,%s)",
            (user_id, today, total_daily_kwh, solar_kwh, daily_budget_kwh, banked)
        )
        db.commit()

    # Get margin bank total
    cursor.execute("SELECT SUM(banked_kwh) as total_banked FROM energy_logs WHERE user_id=%s", (user_id,))
    bank_result = cursor.fetchone()
    total_banked = round(bank_result['total_banked'] or 0, 2)
    total_banked_rs = round(total_banked * per_unit, 2)

    cursor.close()
    db.close()

    return render_template('dashboard.html',
        user=user,
        appliances=appliances,
        total_daily_kwh=total_daily_kwh,
        daily_cost=daily_cost,
        monthly_units=monthly_units,
        monthly_cost=monthly_cost,
        net_monthly_cost=net_monthly_cost,
        monthly_budget_rs=monthly_budget_rs,
        per_unit=per_unit,
        weather=weather,
        solar_kwh=solar_kwh,
        solar_savings=solar_savings,
        banked=banked,
        total_banked=total_banked,
        total_banked_rs=total_banked_rs,
        budget_percent=budget_percent,
        budget_warning=budget_warning,
        budget_exceeded=budget_exceeded,
        chart_labels=json.dumps(chart_labels),
        chart_kwh=json.dumps(chart_kwh),
        chart_cost=json.dumps(chart_cost)
    )

# -------- ADD APPLIANCE --------
@app.route('/add_appliance', methods=['GET', 'POST'])
def add_appliance():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        wattage = int(request.form['wattage'])
        hours = float(request.form['avg_hours_per_day'])
        category = request.form.get('category', 'General')

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "INSERT INTO appliances (user_id, name, wattage, avg_hours_per_day, category) VALUES (%s,%s,%s,%s,%s)",
            (session['user_id'], name, wattage, hours, category)
        )
        db.commit()
        cursor.close()
        db.close()
        flash(f'{name} add ho gaya!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('add_appliance.html')

# -------- DELETE APPLIANCE --------
@app.route('/delete_appliance/<int:appliance_id>')
def delete_appliance(appliance_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("DELETE FROM appliances WHERE id=%s AND user_id=%s", (appliance_id, session['user_id']))
    db.commit()
    cursor.close()
    db.close()
    flash('Appliance delete ho gaya!', 'info')
    return redirect(url_for('dashboard'))

# -------- EDIT PROFILE --------
@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        city = request.form.get('city', 'Rawalpindi')
        monthly_budget_rs = float(request.form.get('monthly_budget_rs', 5000))
        per_unit_cost = float(request.form.get('per_unit_cost', 55))
        solar = 1 if request.form.get('solar_panels') else 0
        panel_count = int(request.form.get('panel_count', 0))
        panel_wattage = int(request.form.get('panel_wattage', 0))

        cursor.execute(
            "UPDATE users SET city=%s, monthly_budget_rs=%s, per_unit_cost=%s, solar_panels=%s, panel_count=%s, panel_wattage=%s WHERE id=%s",
            (city, monthly_budget_rs, per_unit_cost, solar, panel_count, panel_wattage, session['user_id'])
        )
        db.commit()
        session['city'] = city
        flash('Profile update ho gaya!', 'success')
        cursor.close()
        db.close()
        return redirect(url_for('dashboard'))

    cursor.execute("SELECT * FROM users WHERE id=%s", (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()
    db.close()
    return render_template('edit_profile.html', user=user)

# -------- UPDATE APPLIANCE HOURS --------
@app.route('/update_hours', methods=['POST'])
def update_hours():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    data = request.get_json()
    db = get_db()
    cursor = db.cursor(dictionary=True)
    for item in data['appliances']:
        cursor.execute(
            "UPDATE appliances SET avg_hours_per_day=%s WHERE id=%s AND user_id=%s",
            (item['hours'], item['id'], session['user_id'])
        )
    db.commit()
    cursor.close()
    db.close()
    return {'status': 'ok'}

# -------- TIPS PAGE --------
@app.route('/tips')
def tips():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    city = session.get('city', 'Rawalpindi')
    weather = get_weather(city)

    tips_list = []
    if weather['temp'] > 40:
        tips_list.append('🌡️ Aaj bohat garmi hai! AC 26°C pe rakho — har degree se 6% bijli bachti hai.')
        tips_list.append('🪟 Curtains band rakho din mein — kamre ka temperature 3-4°C kam rahega.')
    elif weather['temp'] > 30:
        tips_list.append('🌤️ Moderate garmi hai — pankha use karo, AC ki zarurat nahi.')
    else:
        tips_list.append('😊 Aaj weather acha hai — AC band rakho aur energy bank karo!')

    if weather['clouds'] < 30:
        tips_list.append('☀️ Dhoop bohat hai! Heavy loads (washing machine, iron) abhi chalao — solar maximum generate kar raha hai.')
    elif weather['clouds'] > 70:
        tips_list.append('☁️ Badal hain — heavy appliances raat ke liye defer karo ya kal sunny time pe chalao.')

    tips_list.append('💡 LED bulbs use karo — normal bulbs se 75% kam bijli khaate hain.')
    tips_list.append('🔌 Standby appliances off karo — yeh 10% tak bijli waste karti hain.')
    tips_list.append('⏰ Washing machine aur iron dopahar 11 AM - 2 PM mein chalao jab solar peak pe ho.')

    return render_template('tips.html', tips=tips_list, weather=weather)

# -------- RUN --------
if __name__ == '__main__':
    app.run(debug=True)