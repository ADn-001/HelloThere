from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import math
import time
import logging
from threading import Lock

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory storage
rooms = {}  # {room_id: {roomId, hostLatitude, hostLongitude, timestamp, peers, peerCount}}
peer_to_room = {}  # {peer_id: room_id}
signaling_messages = {}  # {peer_id: [{type, sender, target, data}]}
active_chats = {}  # {peer_id: set([target_peer_ids])}
state_lock = Lock()

# Calculate distance between two coordinates (in meters)
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

@app.route('/broadcast', methods=['POST', 'OPTIONS'])
def broadcast():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    data = request.get_json()
    logger.info(f"[Server] Received request to /broadcast: {data}")
    required_fields = ['hostLatitude', 'hostLongitude', 'timestamp', 'peerId']
    
    if not all(field in data for field in required_fields):
        logger.error(f"[Server] Missing required fields: {data}")
        return jsonify({'error': 'Missing required fields'}), 400
    
    peer_id = data['peerId']
    lat = data['hostLatitude']
    lon = data['hostLongitude']
    timestamp = data['timestamp']
    
    logger.info(f"[Server] Broadcast received from peer_id: {peer_id}, lat: {lat}, lon: {lon}")
    
    with state_lock:
        max_distance = 100
        assigned_room_id = None
        for existing_room_id, room in rooms.items():
            distance = calculate_distance(lat, lon, room['hostLatitude'], room['hostLongitude'])
            logger.info(f"[Server] Checking room {existing_room_id}, distance: {distance}m")
            if distance <= max_distance:
                assigned_room_id = existing_room_id
                break
        
        if assigned_room_id:
            if peer_id not in rooms[assigned_room_id]['peers']:
                rooms[assigned_room_id]['peers'].append(peer_id)
                rooms[assigned_room_id]['peerCount'] = len(rooms[assigned_room_id]['peers'])
                # Notify existing peers of new join (existing peers will initiate offers)
                for other_peer in rooms[assigned_room_id]['peers']:
                    if other_peer != peer_id:
                        if other_peer not in signaling_messages:
                            signaling_messages[other_peer] = []
                        signaling_messages[other_peer].append({
                            'type': 'peer-joined',
                            'sender': peer_id,
                            'target': other_peer
                        })
                        logger.info(f"[Server] Stored peer-joined from {peer_id} to {other_peer} (existing peer will offer)")
                logger.info(f"[Server] Peer {peer_id} added to room {assigned_room_id} as answerer, peers: {rooms[assigned_room_id]['peers']}")
            peer_to_room[peer_id] = assigned_room_id
            response = {
                'status': 'joined',
                'peerList': [p for p in rooms[assigned_room_id]['peers'] if p != peer_id]
            }
        else:
            assigned_room_id = str(uuid.uuid4())
            rooms[assigned_room_id] = {
                'roomId': assigned_room_id,
                'hostLatitude': lat,
                'hostLongitude': lon,
                'timestamp': timestamp,
                'peers': [peer_id],
                'peerCount': 1
            }
            peer_to_room[peer_id] = assigned_room_id
            response = {
                'status': 'created',
                'peerList': []
            }
        
        logger.info(f"[Server] Updated peer_to_room: {peer_to_room}")
        logger.info(f"[Server] Broadcast response: {response}")
        logger.info(f"[Server] Current rooms state: {rooms}")
        return jsonify(response), 200

@app.route('/initiate-group-chat', methods=['POST', 'OPTIONS'])
def initiate_group_chat():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    data = request.get_json()
    logger.info(f"[Server] Received request to /initiate-group-chat: {data}")
    required_fields = ['peerId']
    
    if not all(field in data for field in required_fields):
        logger.error(f"[Server] Missing required fields: {data}")
        return jsonify({'error': 'Missing required fields'}), 400
    
    peer_id = data['peerId']
    
    with state_lock:
        if peer_id not in peer_to_room:
            logger.error(f"[Server] Peer {peer_id} not found in any room")
            return jsonify({'error': 'Peer not found in any room'}), 404
        
        room_id = peer_to_room[peer_id]
        if room_id not in rooms:
            logger.error(f"[Server] Room {room_id} not found for peer {peer_id}")
            del peer_to_room[peer_id]
            return jsonify({'error': 'Room not found'}), 404
        
        peer_list = [p for p in rooms[room_id]['peers'] if p != peer_id]
        # Track active chats
        if peer_id not in active_chats:
            active_chats[peer_id] = set()
        for target_peer_id in peer_list:
            active_chats[peer_id].add(target_peer_id)
            if target_peer_id not in active_chats:
                active_chats[target_peer_id] = set()
            active_chats[target_peer_id].add(peer_id)
        logger.info(f"[Server] Initiated group chat for {peer_id} with peers: {peer_list}")
        return jsonify({'peers': peer_list}), 200

@app.route('/offer', methods=['POST', 'OPTIONS'])
def offer():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    data = request.get_json()
    logger.info(f"[Server] Received request to /offer: {data}")
    required_fields = ['peerId', 'targetPeerIds', 'offer']
    
    if not all(field in data for field in required_fields):
        logger.error(f"[Server] Missing required fields: {data}")
        return jsonify({'error': 'Missing required fields'}), 400
    
    peer_id = data['peerId']
    target_peer_ids = data['targetPeerIds']
    offer = data['offer']
    
    with state_lock:
        if peer_id not in peer_to_room:
            logger.error(f"[Server] Peer {peer_id} not found in any room")
            return jsonify({'error': 'Peer not found'}), 404
        
        room_id = peer_to_room[peer_id]
        for target_peer_id in target_peer_ids:
            if target_peer_id not in peer_to_room or peer_to_room[target_peer_id] != room_id:
                logger.error(f"[Server] Target peer {target_peer_id} not in room {room_id}")
                continue
            if target_peer_id not in signaling_messages:
                signaling_messages[target_peer_id] = []
            signaling_messages[target_peer_id].append({
                'type': 'offer',
                'sender': peer_id,
                'target': target_peer_id,
                'data': offer
            })
            logger.info(f"[Server] Stored offer from {peer_id} to {target_peer_id}")
        return jsonify({'status': 'offers stored'}), 200

@app.route('/answer', methods=['POST', 'OPTIONS'])
def answer():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    data = request.get_json()
    logger.info(f"[Server] Received request to /answer: {data}")
    required_fields = ['peerId', 'targetPeerId', 'answer']
    
    if not all(field in data for field in required_fields):
        logger.error(f"[Server] Missing required fields: {data}")
        return jsonify({'error': 'Missing required fields'}), 400
    
    peer_id = data['peerId']
    target_peer_id = data['targetPeerId']
    answer = data['answer']
    
    with state_lock:
        if peer_id not in peer_to_room or target_peer_id not in peer_to_room:
            logger.error(f"[Server] Peer {peer_id} or target peer {target_peer_id} not found in any room")
            return jsonify({'error': 'Peer or target peer not found'}), 404
        
        room_id = peer_to_room[peer_id]
        if peer_to_room[target_peer_id] != room_id:
            logger.error(f"[Server] Target peer {target_peer_id} not in room {room_id}")
            return jsonify({'error': 'Target peer not in room'}), 404
        
        if target_peer_id not in signaling_messages:
            signaling_messages[target_peer_id] = []
        signaling_messages[target_peer_id].append({
            'type': 'answer',
            'sender': peer_id,
            'target': target_peer_id,
            'data': answer
        })
        logger.info(f"[Server] Stored answer from {peer_id} to {target_peer_id}")
        return jsonify({'status': 'answer stored'}), 200

@app.route('/ice-candidate', methods=['POST', 'OPTIONS'])
def ice_candidate():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    data = request.get_json()
    logger.info(f"[Server] Received request to /ice-candidate: {data}")
    required_fields = ['peerId', 'targetPeerId', 'candidate']
    
    if not all(field in data for field in required_fields):
        logger.error(f"[Server] Missing required fields: {data}")
        return jsonify({'error': 'Missing required fields'}), 400
    
    peer_id = data['peerId']
    target_peer_id = data['targetPeerId']
    candidate = data['candidate']
    
    with state_lock:
        if peer_id not in peer_to_room or target_peer_id not in peer_to_room:
            logger.error(f"[Server] Peer {peer_id} or target peer {target_peer_id} not found in any room")
            return jsonify({'error': 'Peer or target peer not found'}), 404
        
        room_id = peer_to_room[peer_id]
        if peer_to_room[target_peer_id] != room_id:
            logger.error(f"[Server] Target peer {target_peer_id} not in room {room_id}")
            return jsonify({'error': 'Target peer not in room'}), 404
        
        if target_peer_id not in signaling_messages:
            signaling_messages[target_peer_id] = []
        signaling_messages[target_peer_id].append({
            'type': 'ice-candidate',
            'sender': peer_id,
            'target': target_peer_id,
            'data': candidate
        })
        logger.info(f"[Server] Stored ICE candidate from {peer_id} to {target_peer_id}")
        return jsonify({'status': 'candidate stored'}), 200

@app.route('/get-signaling-messages', methods=['POST', 'OPTIONS'])
def get_signaling_messages():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    data = request.get_json()
    logger.info(f"[Server] Received request to /get-signaling-messages: {data}")
    if 'peerId' not in data:
        logger.error(f"[Server] Missing peerId: {data}")
        return jsonify({'error': 'Missing peerId'}), 400
    
    peer_id = data['peerId']
    with state_lock:
        messages = signaling_messages.get(peer_id, [])
        signaling_messages[peer_id] = []
        logger.info(f"[Server] Sent {len(messages)} signaling messages to peer {peer_id}: {messages}")
        return jsonify({'messages': messages}), 200

@app.route('/leave', methods=['POST', 'OPTIONS'])
def leave():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    data = request.get_json()
    logger.info(f"[Server] Received request to /leave: {data}")
    required_fields = ['peerId']
    
    if not all(field in data for field in required_fields):
        logger.error(f"[Server] Missing required fields: {data}")
        return jsonify({'error': 'Missing required fields'}), 400
    
    peer_id = data['peerId']
    
    with state_lock:
        if peer_id not in peer_to_room:
            logger.error(f"[Server] Peer {peer_id} not found in any room")
            return jsonify({'error': 'Peer not found in any room'}), 404
        
        room_id = peer_to_room[peer_id]
        if room_id not in rooms or peer_id not in rooms[room_id]['peers']:
            logger.error(f"[Server] Room {room_id} or peer {peer_id} not found")
            del peer_to_room[peer_id]
            return jsonify({'error': 'Room or peer not found'}), 404
        
        rooms[room_id]['peers'].remove(peer_id)
        rooms[room_id]['peerCount'] = len(rooms[room_id]['peers'])
        # Notify remaining peers
        for other_peer in rooms[room_id]['peers']:
            if other_peer not in signaling_messages:
                signaling_messages[other_peer] = []
            signaling_messages[other_peer].append({
                'type': 'peer-left',
                'sender': peer_id,
                'target': other_peer
            })
        if rooms[room_id]['peerCount'] == 0:
            logger.info(f"[Server] Room {room_id} empty, removing")
            del rooms[room_id]
        
        del peer_to_room[peer_id]
        
        if peer_id in active_chats:
            for target_peer_id in active_chats[peer_id]:
                if target_peer_id in active_chats:
                    active_chats[target_peer_id].discard(peer_id)
                    if not active_chats[target_peer_id]:
                        del active_chats[target_peer_id]
                if target_peer_id not in signaling_messages:
                    signaling_messages[target_peer_id] = []
                signaling_messages[target_peer_id].append({
                    'type': 'peer-left',
                    'sender': peer_id,
                    'target': target_peer_id
                })
            del active_chats[peer_id]
        
        logger.info(f"[Server] Peer {peer_id} left room {room_id}, peer_to_room: {peer_to_room}")
        logger.info(f"[Server] Current rooms state: {rooms}")
        return jsonify({'status': 'left'}), 200

@app.route('/check_location', methods=['POST', 'OPTIONS'])
def check_location():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    data = request.get_json()
    logger.info(f"[Server] Received request to /check_location: {data}")
    required_fields = ['latitude', 'longitude', 'peerId']
    
    if not all(field in data for field in required_fields):
        logger.error(f"[Server] Missing required fields: {data}")
        return jsonify({'error': 'Missing required fields'}), 400
    
    peer_id = data['peerId']
    lat = data['latitude']
    lon = data['longitude']
    
    with state_lock:
        if peer_id not in peer_to_room:
            logger.error(f"[Server] Peer {peer_id} not found in any room")
            return jsonify({'status': 'removed'}), 200
        
        room_id = peer_to_room[peer_id]
        if room_id not in rooms:
            logger.error(f"[Server] Room {room_id} not found for peer {peer_id}")
            del peer_to_room[peer_id]
            return jsonify({'status': 'removed'}), 200
        
        max_distance = 100
        room = rooms[room_id]
        distance = calculate_distance(lat, lon, room['hostLatitude'], room['hostLongitude'])
        if distance > max_distance:
            logger.info(f"[Server] Peer {peer_id} removed from room {room_id}, distance: {distance}m")
            rooms[room_id]['peers'].remove(peer_id)
            rooms[room_id]['peerCount'] = len(rooms[room_id]['peers'])
            for other_peer in rooms[room_id]['peers']:
                if other_peer not in signaling_messages:
                    signaling_messages[other_peer] = []
                signaling_messages[other_peer].append({
                    'type': 'peer-left',
                    'sender': peer_id,
                    'target': other_peer
                })
            if rooms[room_id]['peerCount'] == 0:
                logger.info(f"[Server] Room {room_id} empty, removing")
                del rooms[room_id]
            del peer_to_room[peer_id]
            if peer_id in active_chats:
                for target_peer_id in active_chats[peer_id]:
                    if target_peer_id in active_chats:
                        active_chats[target_peer_id].discard(peer_id)
                        if not active_chats[target_peer_id]:
                            del active_chats[target_peer_id]
                    if target_peer_id not in signaling_messages:
                        signaling_messages[target_peer_id] = []
                    signaling_messages[target_peer_id].append({
                        'type': 'peer-left',
                        'sender': peer_id,
                        'target': target_peer_id
                    })
                del active_chats[peer_id]
            logger.info(f"[Server] Updated peer_to_room: {peer_to_room}")
            return jsonify({'status': 'removed'}), 200
        
        logger.info(f"[Server] Peer {peer_id} remains in room {room_id}, distance: {distance}m")
        return jsonify({'status': 'ok'}), 200

@app.route('/debug_rooms', methods=['GET'])
def debug_rooms():
    with state_lock:
        logger.info(f"[Server] Current rooms state: {rooms}")
        return jsonify(rooms), 200

@app.route('/debug_peers', methods=['GET'])
def debug_peers():
    room_id = request.args.get('roomId')
    if not room_id:
        logger.error("[Server] Missing roomId in /debug_peers request")
        return jsonify({'error': 'Missing roomId'}), 400
    with state_lock:
        if room_id not in rooms:
            logger.error(f"[Server] Room {room_id} not found in /debug_peers")
            return jsonify({'error': 'Room not found'}), 404
        logger.info(f"[Server] Peers in room {room_id}: {rooms[room_id]['peers']}")
        return jsonify({'peers': rooms[room_id]['peers']}), 200

@app.route('/debug_peer_to_room', methods=['GET'])
def debug_peer_to_room():
    with state_lock:
        logger.info(f"[Server] Current peer_to_room state: {peer_to_room}")
        return jsonify(peer_to_room), 200

def cleanup_stale_rooms():
    stale_threshold = 3600  # 1 hour
    current_time = time.time()
    with state_lock:
        for room_id in list(rooms.keys()):
            room = rooms[room_id]
            room_age = current_time - time.mktime(time.strptime(room['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ'))
            if room_age > stale_threshold and room['peerCount'] == 0:
                logger.info(f"[Server] Removing stale room {room_id}")
                del rooms[room_id]

if __name__ == '__main__':
    from threading import Timer
    def run_cleanup():
        cleanup_stale_rooms()
        Timer(600, run_cleanup).start()
    run_cleanup()
    app.run(ssl_context=('cert/server.crt', 'cert/server.key'), host='0.0.0.0', port=5000)