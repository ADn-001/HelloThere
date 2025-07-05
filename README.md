# Hello-There: A Proximity Chat App – Getting Started (Development Version)

By:

## Adnan Mohammed Shelim

## Vladimir Drevin

## Alex Brijo Sebastian

## Fedor Ryzhenkov

This is the development branch of Hello-There, for the production branch, switch to "Master"
The guide below provides step-by-step instructions to set up, run, and use the development version of the **Proximity Chat App**, a decentralized, proximity-based chat application.

The app uses:

* A **Flask backend** for signaling
* A **Create React App (CRA)** frontend (deployable as a PWA)
* **WebRTC** for peer-to-peer communication
* **Geolocation APIs** for proximity detection

---

## 📦 Project Overview

### Frontend

* Built with **Create React App (CRA)** for a **Progressive Web App (PWA)**
* Uses **React**, **WebRTC**, and **Browser Geolocation API**

### Backend

* **Flask** server for WebRTC signaling
* Uses `flask-cors` for CORS handling
* Runs locally with **gunicorn** and **gevent**

### Tech Stack

| Layer    | Stack                                              |
| -------- | -------------------------------------------------- |
| Frontend | JavaScript, React, WebRTC, Browser Geolocation API |
| Backend  | Python, Flask, flask-cors                          |

### Local Setup

* Frontend: `https://localhost:3000`
* Backend: `https://localhost:5000`
* Uses **mkcert** to generate a **self-signed SSL certificate**.

---

## ✅ Prerequisites

Make sure your Ubuntu system has the following installed:

* **Git**: `sudo apt install git`
* **Python 3.12.3**: `sudo apt install python3.12 python3.12-venv`
* **Node.js 18**:

  ```bash
  curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
  sudo apt install -y nodejs
  ```
* **npm**: Comes with Node.js (`npm -v`)
* **mkcert**:

  ```bash
  sudo apt install libnss3-tools
  wget https://github.com/FiloSottile/mkcert/releases/download/v1.4.4/mkcert-v1.4.4-linux-amd64
  sudo mv mkcert-v1.4.4-linux-amd64 /usr/local/bin/mkcert
  sudo chmod +x /usr/local/bin/mkcert
  ```
* **Google Chrome**: `sudo apt install google-chrome-stable`

---

## ⚙️ Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/<your-username>/proximity-chat-app.git
cd proximity-chat-app
```

Replace `<your-username>` with your GitHub username.

Project structure:

```
server/      # Flask backend
client/      # CRA frontend
render.yaml  # Deployment config (not used locally)
```

---

### 2. Set Up the Backend

#### Create and Activate Virtual Environment

```bash
cd server
python3.12 -m venv venv
source venv/bin/activate
```

#### Install Dependencies

```bash
pip install -r requirements.txt
```

**Expected packages**:

* flask==2.0.1
* flask-cors==3.0.10
* gevent==24.2.1
* greenlet==3.1.1
* gunicorn==22.0.0
* werkzeug==2.2.3

---

### 3. Create SSL Certificate (with `mkcert`)

```bash
mkdir -p .cert
cd .cert
mkcert localhost
```

This creates:

* `localhost.pem` (certificate)
* `localhost-key.pem` (key)

Update `.gitignore`:

```bash
echo ".cert/" >> ../.gitignore
```

---

### 4. Trust mkcert Certificate in Chrome

1. Open `chrome://settings/security`

2. Click **Manage certificates**

3. Go to **Trusted Root Certification Authorities**

4. If not already trusted, import:

   ```
   ~/.local/share/mkcert/rootCA.pem
   ```

5. Restart Chrome

To verify, visit:

```
https://localhost:5000/debug_peer_to_room
```

---

### 5. Set Up the Frontend

```bash
cd ../../client
npm install
npm list --depth=0
```

---

### 6. Run the Backend

```bash
cd ../server
source venv/bin/activate
python app.py
```

Ensure `app.py` includes:

```python
ssl_context=('.cert/localhost.pem', '.cert/localhost-key.pem')
```

Expected output:

```
* Running on https://localhost:5000
```

Test with:

```bash
curl -k https://localhost:5000/debug_peer_to_room
```

---

### 7. Run the Frontend

Open a new terminal:

```bash
cd proximity-chat-app/client
npm start
```

Opens browser at `http://localhost:3000`.

---

### 8. Use the Client

#### Open Two Browser Windows

* Chrome (2 tabs) or
* Chrome + Firefox

#### Set Geolocation

* Open DevTools → More Tools → **Sensors**
* Set location to:

  ```
  Latitude: 41.7234944
  Longitude: 44.7807488
  ```

#### Assign Peer IDs

Edit `client/src/App.jsx`:

```jsx
<RoomManager peerId="peer1" />
```

#### Connect to a Room

Click **Connect** in both windows.

Expected:

* Loader disappears
* “Room joined” popup
* “Connected to 1 peer(s)” displayed

#### Send Messages

Type and send a message.

Expected:

* Styled messages (green for self, gray for other)

#### Leave the Room

Click **✕ Leave**

Expected:

* Loader reappears
* Peer count updates to 0

#### Test PWA

* Click **+ icon** in Chrome to install the PWA
* Launch offline to test graceful failure

---

## 🧪 Troubleshooting

| Issue                     | Fix                                                                                     |
| ------------------------- | --------------------------------------------------------------------------------------- |
| Backend fails to start    | Check for `ImportError`. Run `pip check`. Ensure `.cert/*.pem` files exist              |
| CORS errors               | Ensure: `CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})`            |
| Chrome shows “Not Secure” | Ensure mkcert root cert is trusted. Re-run `mkcert -install` if needed                  |
| Frontend can’t connect    | Check fetch URLs in `RoomManager.jsx`. Backend must be running                          |
| WebRTC not working        | Check `client/src/utils/webrtc.js` config. Ensure permissions for mic, camera, location |

---

## 📝 Additional Notes
* **Local vs Production**:

  | Local                                            | Production (Render)                                                                          |
  | ------------------------------------------------ | -------------------------------------------------------------------------------------------- |
  | [http://localhost:3000](http://localhost:3000)   | [https://proximity-chat-frontend.onrender.com](https://proximity-chat-frontend.onrender.com) |
  | [https://localhost:5000](https://localhost:5000) | [https://proximity-chat-backend.onrender.com](https://proximity-chat-backend.onrender.com)   |


