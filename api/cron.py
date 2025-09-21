# api/cron.py

import os
from flask import Flask, request, jsonify
from supabase import create_client, Client
from .gpx_function import analyze_gpx_data # Import the refactored function

# --- Initializations ---
app = Flask(__name__)
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(url, key)
CRON_SECRET = os.environ.get("CRON_SECRET")

@app.route('/api/cron', methods=['POST'])
def process_pending_drive():
    # 1. Secure the endpoint
    auth_header = request.headers.get('Authorization')
    if auth_header != f'Bearer {CRON_SECRET}':
        return jsonify({"error": "Unauthorized"}), 401
    
    drive_id = None
    try:
        # 2. Find one 'pending' drive
        pending_drive_res = supabase.table("drives").select("*").eq("status", "pending").limit(1).single().execute()
        
        if not pending_drive_res.data:
            return jsonify({"message": "No pending drives to process."}), 200
        
        drive = pending_drive_res.data
        drive_id = drive['id']
        file_path = drive['file_path']

        # 3. Mark as 'processing' to prevent re-processing
        supabase.table("drives").update({"status": "processing"}).eq("id", drive_id).execute()

        # 4. Download the file from Storage
        gpx_file_content = supabase.storage.from_("gpx_files").download(file_path)

        # 5. Run the analysis
        stats_dict = analyze_gpx_data(gpx_file_content)
        stats_dict['drive_id'] = drive_id # Link stats to the drive

        # 6. Save results to 'drive_stats' table
        supabase.table("drive_stats").insert(stats_dict).execute()

        # 7. Update the drive 'status' to 'completed'
        supabase.table("drives").update({"status": "completed"}).eq("id", drive_id).execute()

        return jsonify({"message": f"Successfully processed drive_id: {drive_id}"}), 200

    except Exception as e:
        # If anything fails, mark the drive as 'failed'
        if drive_id:
            supabase.table("drives").update({"status": "failed"}).eq("id", drive_id).execute()
        
        # Log the error (in a real app, you'd use a logging service)
        print(f"Error processing drive {drive_id}: {str(e)}")
        return jsonify({"error": "Failed to process drive", "details": str(e)}), 500
