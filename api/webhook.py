import asyncio
import os
import sys
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram.ext import Application
from bot import setup_bot_handlers, TOKEN

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# To make the handler work with different execution environments
current_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_path)

async def handler(request_body):
    """Handles an incoming Telegram webhook update."""
    app = Application.builder().token(TOKEN).build()
    setup_bot_handlers(app)

    try:
        update = json.loads(request_body.decode('utf-8'))
        await app.process_update(update)
    except Exception as e:
        logger.error(f"Error processing update: {e}")

class RequestHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests from Vercel."""
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        request_body = self.rfile.read(content_length)
        
        asyncio.run(handler(request_body))
        
        self.send_response(200)
        self.end_headers()

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', int(os.environ.get('PORT', 8080))), RequestHandler)
    server.serve_forever()
