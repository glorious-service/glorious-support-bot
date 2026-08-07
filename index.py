import os
import json
import sys
import logging
from http.server import BaseHTTPRequestHandler
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import your bot setup function
from bot import setup_bot, BOT_TOKEN
from telegram import Update

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global application instance
_app = None

def get_bot_app():
    """Get or create bot application instance"""
    global _app
    if _app is None:
        try:
            _app = setup_bot()
            logger.info("✅ Bot application initialized for Vercel")
        except Exception as e:
            logger.error(f"❌ Failed to initialize bot: {e}")
            raise
    return _app

class handler(BaseHTTPRequestHandler):
    """
    Vercel serverless function handler for Telegram webhook.
    """
    
    def do_GET(self):
        """Handle GET requests (health check)"""
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            response = {
                'status': 'ok',
                'message': 'Bot is running on Vercel',
                'timestamp': datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
        except Exception as e:
            logger.error(f"GET error: {e}")
            self.send_error(500, str(e))
        return

    def do_POST(self):
        """Handle POST requests (Telegram webhook)"""
        try:
            # Read the request body
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            if not post_data:
                logger.warning("Empty request body received")
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Empty request body'}).encode('utf-8'))
                return

            # Parse the update
            try:
                update_data = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Invalid JSON'}).encode('utf-8'))
                return

            # Get bot application
            app = get_bot_app()
            
            # Process the update
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                update = Update.de_json(update_data, app.bot)
                loop.run_until_complete(app.process_update(update))
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'ok'}).encode('utf-8'))
                logger.info(f"✅ Processed update: {update.update_id if update else 'unknown'}")
            except Exception as e:
                logger.error(f"Error processing update: {e}", exc_info=True)
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Webhook error: {e}", exc_info=True)
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))

    def do_HEAD(self):
        """Handle HEAD requests"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        return

    def log_message(self, format, *args):
        """Override to use logger"""
        logger.info(f"{self.address_string()} - {format % args}")