import os
import json
import sys
import logging
from http.server import BaseHTTPRequestHandler

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import bot application
from bot import get_app, setup_bot, BOT_TOKEN
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
        _app = setup_bot()
        # Disable polling for Vercel
        logger.info("✅ Bot application initialized for Vercel")
    return _app

def handler(request):
    """
    Vercel serverless function handler
    """
    try:
        # Handle GET requests (health check)
        if request.method == 'GET':
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'status': 'ok',
                    'message': 'Bot is running on Vercel',
                    'timestamp': datetime.now().isoformat()
                }),
                'headers': {
                    'Content-Type': 'application/json'
                }
            }
        
        # Handle POST requests (webhook)
        if request.method == 'POST':
            # Get the request body
            body = request.get_data(as_text=True)
            if not body:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Empty request body'})
                }
            
            # Parse the update
            update_data = json.loads(body)
            
            # Get bot application
            app = get_bot_app()
            
            # Process the update
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Create Update object
                update = Update.de_json(update_data, app.bot)
                
                # Process the update
                loop.run_until_complete(app.process_update(update))
                
                return {
                    'statusCode': 200,
                    'body': json.dumps({'status': 'ok'})
                }
            finally:
                loop.close()
        
        # Method not allowed
        return {
            'statusCode': 405,
            'body': json.dumps({'error': 'Method not allowed'})
        }
        
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'status': 'error'
            })
        }

# For local testing with Flask
if __name__ == "__main__":
    from flask import Flask, request, jsonify
    from datetime import datetime
    
    app = Flask(__name__)
    
    @app.route('/webhook', methods=['POST'])
    def webhook():
        # Create a mock request object
        class MockRequest:
            method = 'POST'
            def get_data(self, as_text=False):
                return request.get_data(as_text=as_text)
        
        result = handler(MockRequest())
        return jsonify(json.loads(result['body'])), result['statusCode']
    
    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({
            'status': 'ok',
            'message': 'Bot is running',
            'timestamp': datetime.now().isoformat()
        })
    
    @app.route('/', methods=['GET'])
    def index():
        return jsonify({
            'status': 'ok',
            'message': 'Glorious PLC Support Bot',
            'endpoints': [
                '/webhook - POST (Telegram webhook)',
                '/health - GET (Health check)',
                '/ - GET (Info)'
            ]
        })
    
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)