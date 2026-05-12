from waitress import serve
from app import app
import os

if __name__ == '__main__':
    # You can change the port here if needed
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting server on port {port}...")
    serve(app, host='0.0.0.0', port=port)
