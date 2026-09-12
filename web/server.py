import http.server
import socketserver
import json
import csv
import os

PORT = 8080
DIRECTORY = os.path.join(os.path.dirname(__file__), "..", "web")
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "..", "output.csv")

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        if self.path == "/api/data":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            data = []
            if os.path.exists(OUTPUT_CSV):
                with open(OUTPUT_CSV, mode="r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        data.append(row)
            self.wfile.write(json.dumps(data).encode("utf-8"))
        else:
            super().do_GET()

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), CustomHandler) as httpd:
        print(f"Server started at http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")
