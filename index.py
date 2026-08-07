import json
import logging
from http.server import BaseHTTPRequestHandler

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class handler(BaseHTTPRequestHandler):
    """
    A minimal webhook handler to test POST requests.
    """
    
    def do_GET(self):
        """Handle GET requests for health checks."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = {
            'status': 'ok',
            'message': 'Webhook endpoint is alive',
            'method': 'GET'
        }
        self.wfile.write(json.dumps(response).encode('utf-8'))
        logger.info("GET request received and handled.")

    def do_POST(self):
        """Handle POST requests from Telegram."""
        logger.info("POST request received!")  # This is the key log line we need to see
        
        try:
            # Read the request body
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            # Log the raw data for debugging
            logger.info(f"Received POST data: {post_data[:200]}...")  # Log first 200 chars
            
            # Try to parse as JSON
            if post_data:
                update_data = json.loads(post_data.decode('utf-8'))
                logger.info(f"Parsed update: {update_data.get('update_id', 'unknown')}")
            
            # Always respond with 200 OK to Telegram
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok', 'message': 'Update received'}).encode('utf-8'))
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received: {e}")
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Invalid JSON'}).encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Error processing POST request: {e}")
            # Still return 200 to avoid Telegram retrying constantly
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode('utf-8'))

    def do_HEAD(self):
        """Handle HEAD requests."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        return

    def log_message(self, format, *args):
        """Override to use logger."""
        logger.info(f"{self.address_string()} - {format % args}")