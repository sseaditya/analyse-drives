# api/index.py

import os
import uuid
from flask import Flask, request, jsonify
from supabase import create_client, Client
from functools import wraps

# --- Initialization ---
app = Flask(__name__)
url: str = os.environ.get("https://fdujrbmufqmpfisscclk.supabase.co")
key: str = os.environ.get("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZkdWpyYm11ZnFtcGZpc3NjY2xrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NjgzNDU5MCwiZXhwIjoyMDcyNDEwNTkwfQ.b-vfRYY416A5hKB7V1DKvtiOw8ga7Y6ALGuJ2SXlBdA") # Use the secure service role key
supabase: Client = create_client(url, key)

# --- Authentication Decorator ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization header is missing or invalid"}), 401
        
        token = auth_header.split(' ')[1]
        try:
            user_response = supabase.auth.get_user(token)
            user = user_response.user
            if not user:
                 raise Exception("User not found")
        except Exception as e:
            return jsonify({"error": "Invalid token", "details": str(e)}), 401
        
        # Pass user object to the decorated function
        return f(user, *args, **kwargs)
    return decorated

# --- API Endpoints ---
@app.route('/api/upload', methods=['POST'])
@token_required
def upload_drive(user):
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    try:
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        if file_extension != 'gpx':
            return jsonify({"error": "Invalid file type, please upload a .gpx file"}), 400

        user_id = user.id
        file_path = f"{user_id}/{uuid.uuid4()}.gpx"
        
        # Upload to Supabase Storage
        supabase.storage.from_("gpx_files").upload(file_path, file.read())
        
        # Create entry in 'drives' table
        drive_data = {
            "user_id": user_id,
            "file_path": file_path,
            "status": "pending",
            "drive_name": file.filename
        }
        inserted_drive = supabase.table("drives").insert(drive_data).execute()

        return jsonify({"message": "File uploaded successfully. Analysis is pending.", "drive_id": inserted_drive.data[0]['id']}), 202

    except Exception as e:
        return jsonify({"error": "An internal error occurred", "details": str(e)}), 500

@app.route('/api/drives', methods=['GET'])
@token_required
def get_drives(user):
    try:
        # Fetch drives and their corresponding stats for the authenticated user
        query = supabase.table("drives").select("*, drive_stats(*)").eq("user_id", user.id).order("uploaded_at", desc=True)
        result = query.execute()
        return jsonify(result.data), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch drives", "details": str(e)}), 500

@app.route('/api/stats/cumulative', methods=['GET'])
@token_required
def get_cumulative_stats(user):
    try:
        # Fetch all completed drive stats for the user
        # Note: This RPC 'get_cumulative_stats' needs to be created in your Supabase SQL Editor for performance.
        # See SQL function details below this code block.
        result = supabase.rpc('get_cumulative_stats', {'p_user_id': user.id}).execute()
        
        if not result.data:
            return jsonify({"total_distance_km": 0, "total_drives": 0}), 200
            
        return jsonify(result.data[0]), 200
    except Exception as e:
        return jsonify({"error": "Failed to calculate cumulative stats", "details": str(e)}), 500