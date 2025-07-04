Proximity Chat App
Setup Instructions

Clone the Repository:
git clone <repository-url>
cd proximity-chat-app


Backend Setup (Flask Server):
cd server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt


Generate Self-Signed Certificates:
mkdir cert
openssl req -x509 -newkey rsa:4096 -nodes -out cert/server.crt -keyout cert/server.key -days 365


Run Flask Server:
python app.py


Frontend Setup (Create React App):
cd ../client
npm install
npm start


Access the App:

Open http://localhost:3000 in a browser.
Allow geolocation permissions.
Trust the self-signed certificate for https://localhost:5000 if prompted.
The app will search for or create a room based on proximity.



Notes

The Flask server runs on https://localhost:5000.
The frontend uses Create React App and runs on http://localhost:3000.
WebRTC signaling is simplified; enhance /webrtc.js for production.
To build for production: npm run build in the client folder.
