import cv2
import torch
import numpy as np
from PIL import Image
from transformers import AutoImageProcessor, Dinov2Model
from sklearn.metrics.pairwise import cosine_similarity
from flask import Flask, request, jsonify
from flask_cors import CORS
import io
import base64
import threading
import multiprocessing
import uuid
from flask import send_from_directory
from simulation_runner import run_openfoam_simulation
from optimization_runner import run_binary_search_optimization, run_ga_optimization
import json
import os

USE_MOCK_CHATBOT = True

if USE_MOCK_CHATBOT:
    from chatbot.mock_chatbot import MockChatBot as ChatBot
else:
    from chatbot.chatbot import ChatBot


# --- 1. Model Loading & Global Setup ---
print("Loading DINOv2 model...")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DINO_PROCESSOR = AutoImageProcessor.from_pretrained("facebook/dinov2-base")
DINO_MODEL = Dinov2Model.from_pretrained("facebook/dinov2-base").to(DEVICE).eval()
print(f"DINOv2 model loaded on {DEVICE}.")

app = Flask(__name__)
# CORS is essential for letting the React frontend talk to this API
CORS(app)
app.static_folder = 'dist/assets'
manager = multiprocessing.Manager()
simulations_db = manager.dict()
chat_sessions = manager.dict()
mock_chat_sessions_store = {}

# --- 2. Core Computer Vision & AI Functions (from your reference code) ---

# REMOVED: find_contours_from_image_bytes

# ADDED: find_room_and_objects_from_image_bytes
def find_room_and_objects_from_image_bytes(image_bytes):
    """
    Reads image bytes, finds the room contour and object contours,
    and returns them in a JSON-serializable format.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    h, w, _ = img.shape
    total_area = h * w
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    blurred_gray = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(gray, 50, 110)
    close_kernel = np.ones((2, 2), np.uint8)
    closed_mask = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, close_kernel)
    all_contours, _ = cv2.findContours(closed_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    #_, thresh = cv2.threshold(gray, 225, 255, cv2.THRESH_BINARY_INV)
    #all_contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    # Find room contour (largest contour, but not the whole image)
    room_contour_raw = max((cnt for cnt in all_contours), key=cv2.contourArea, default=None)
    if room_contour_raw is not None and cv2.contourArea(room_contour_raw) > total_area * 0.95:
        room_contour_raw = None

    # Serialize room contour
    serializable_room_contour = None
    if room_contour_raw is not None:
        serializable_room_contour = {
            "id": "room_0",
            "points": room_contour_raw.squeeze().tolist()
        }

    # Filter object contours
    min_area, max_area = total_area/4000, total_area/4
    object_contours = []
    for cnt in all_contours:
        is_object_size = min_area < cv2.contourArea(cnt) < max_area
        is_not_room = True
        if room_contour_raw is not None and np.array_equal(cnt, room_contour_raw):
            is_not_room = False
        
        if is_object_size and is_not_room:
            object_contours.append(cnt)

    # Convert object contours to a simple list of points for JSON
    serializable_object_contours = []
    for i, contour in enumerate(object_contours):
        points = contour.squeeze().tolist()
        serializable_object_contours.append({
            "id": f"contour_{i}",
            "points": points
        })

    return serializable_room_contour, serializable_object_contours, img


def get_image_embedding(image_rgb, contour_points):
    """Crops an image based on a contour and gets its DINOv2 embedding."""
    contour = np.array(contour_points).astype(np.int32)
    x, y, w, h = cv2.boundingRect(contour)
    if w <= 1 or h <= 1: return None
    
    cropped_image = image_rgb[y:y+h, x:x+w]
    inputs = DINO_PROCESSOR(images=cropped_image, return_tensors="pt").to(DEVICE)
    with torch.no_grad():
        outputs = DINO_MODEL(**inputs)
        return outputs.pooler_output

# --- 3. Flask API Endpoints ---

@app.route('/api/process-image', methods=['POST'])
def process_image_endpoint():
    """
    Endpoint for Step 1.
    Receives an image file, finds contours, and returns them.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    image_bytes = file.read()
    # Also return the image as base64 so frontend can display it without storing it
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    
    # MODIFIED: Use the new function
    room_contour, object_contours, _ = find_room_and_objects_from_image_bytes(image_bytes)

    # MODIFIED: Return the room contour as well
    return jsonify({
        "image_b64": image_base64,
        "contours": object_contours,
        "room_contour": room_contour,
    })

@app.route('/api/autofill', methods=['POST'])
def autofill_endpoint():
    """
    Endpoint for Step 2 Autofill.
    Receives the image, user-classified examples, and unclassified contours.
    Returns new classifications based on DINOv2 similarity.
    """
    data = request.json
    image_b64 = data['image_b64']
    example_objects = data['example_objects']
    unclassified_contours = data['unclassified_contours']
    
    # Decode image
    image_bytes = base64.b64decode(image_b64)
    nparr = np.frombuffer(image_bytes, np.uint8)
    img_rgb = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # 1. Create reference embeddings from user examples
    category_embeddings = {}
    for obj in example_objects:
        embedding = get_image_embedding(img_rgb, obj['contour']['points'])
        if embedding is not None:
            if obj['category'] not in category_embeddings:
                category_embeddings[obj['category']] = []
            category_embeddings[obj['category']].append(embedding)

    # Average embeddings for each category for robustness
    avg_category_embeddings = {
        cat: torch.mean(torch.stack(embs), dim=0) 
        for cat, embs in category_embeddings.items()
    }

    # 2. Classify unclassified contours
    newly_classified = []
    for contour_obj in unclassified_contours:
        contour_embedding = get_image_embedding(img_rgb, contour_obj['points'])
        if contour_embedding is None:
            continue

        best_cat, max_sim = None, -1.0
        for cat, cat_emb in avg_category_embeddings.items():
            sim = cosine_similarity(contour_embedding.cpu().numpy(), cat_emb.cpu().numpy())[0][0]
            if sim > max_sim:
                max_sim, best_cat = sim, cat
        
        # Using a fixed threshold from your reference code
        if best_cat and max_sim >= 0.8:
            newly_classified.append({
                "id": contour_obj['id'],
                "category": best_cat
            })
            
    return jsonify({"newly_classified": newly_classified})

@app.route('/api/run-simulation', methods=['POST'])
def run_simulation_endpoint():
    config = request.json
    run_id = str(uuid.uuid4())

    if 'physics' not in config:
        config['physics'] = {}

    # Use multiprocessing.Process instead of threading.Thread
    # The 'simulations_db' is now a special managed dictionary that can be passed to the new process
    process = multiprocessing.Process(
        target=run_openfoam_simulation, 
        args=(config, run_id, simulations_db)
    )
    process.start()
    
    # Set the initial status in the shared dictionary
    simulations_db[run_id] = "running"
    
    return jsonify({"message": "Simulation started", "run_id": run_id}), 202

@app.route('/api/run-binary-search', methods=['POST'])
def run_binary_search_endpoint():
    """Endpoint to start a binary search optimization for CRAC temperature."""
    config = request.json
    run_id = str(uuid.uuid4())
    process = multiprocessing.Process(
        target=run_binary_search_optimization,
        args=(config, run_id, simulations_db)
    )
    process.start()
    simulations_db[run_id] = "running_optimization"
    return jsonify({"message": "Binary search optimization started", "run_id": run_id}), 202

@app.route('/api/run-ga-optimization', methods=['POST'])
def run_ga_endpoint():
    """Endpoint to start a genetic algorithm optimization for layout."""
    config = request.json
    run_id = str(uuid.uuid4())
    process = multiprocessing.Process(
        target=run_ga_optimization,
        args=(config, run_id, simulations_db)
    )
    process.start()
    simulations_db[run_id] = "running_optimization"
    return jsonify({"message": "Genetic algorithm optimization started", "run_id": run_id}), 202

# --- NEW: CHATBOT ENDPOINTS ---
def get_chatbot_for_session(session_id):
    """Creates or retrieves a chatbot instance for a given session ID."""
    if USE_MOCK_CHATBOT:
        if session_id not in mock_chat_sessions_store:
            # The parameters don't matter for the mock bot
            mock_chat_sessions_store[session_id] = ChatBot(None, None)
        return mock_chat_sessions_store[session_id]
    else:
        # This is the original logic for the real VLLM chatbot
        if session_id not in chat_sessions:
            with open(os.path.join('chatbot', 'schema.json'), 'r', encoding='utf-8') as f:
                schema = f.read()
            bot = ChatBot('meta-llama/Llama-3.2-3B-Instruct', schema=schema, port=8000)
            # Store the serializable message list, NOT the bot object itself
            chat_sessions[session_id] = bot.messages
        
        # Re-create a bot instance and load its history for the current request
        bot = ChatBot('meta-llama/Llama-3.2-3B-Instruct', schema="", port=8000)
        bot.messages = chat_sessions[session_id]
        return bot


@app.route('/api/chat/send', methods=['POST'])
def chat_endpoint():
    data = request.json
    session_id = data.get('session_id', str(uuid.uuid4()))
    user_message = data.get('message')

    if not user_message:
        return jsonify({"error": "message is required"}), 400

    bot = get_chatbot_for_session(session_id)
    
    response_content = bot.send_user_message(user_message, stream=False)
    
    # For the real bot, we need to save the updated message history
    if not USE_MOCK_CHATBOT:
        chat_sessions[session_id] = bot.messages

    try:
        parsed_response = json.loads(response_content)
        return jsonify({"reply": parsed_response, "session_id": session_id})
    except json.JSONDecodeError:
        # This case is more for the real LLM which might not return perfect JSON
        return jsonify({"reply": response_content, "session_id": session_id})

@app.route('/api/simulation-status/<run_id>', methods=['GET'])
def simulation_status_endpoint(run_id):
    # This now reads from the shared multiprocessing dictionary
    status = simulations_db.get(run_id, "not_found")
    # print(status)
    # print(str(status))
    return jsonify({"run_id": run_id, "status": status})

@app.route('/api/get-result/<run_id>/<filename>', methods=['GET'])
def get_result_file(run_id, filename):
    """Serves the converted .gltf files."""
    directory = os.path.abspath(os.path.join('simulations', run_id))
    response = send_from_directory(directory, filename)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'dist'))
    if path != "" and os.path.exists(os.path.join(dist_dir, path)):
        return send_from_directory(dist_dir, path)
    else:
        return send_from_directory(dist_dir, 'index.html')

if __name__ == '__main__':
    # host='0.0.0.0' makes the API accessible from other devices on your network
    app.run(debug=True, host='0.0.0.0', port=5000)