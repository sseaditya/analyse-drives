import os
from supabase import create_client, Client

# --- IMPORTANT ---
# You need the ANON KEY for this, NOT the service key.
# Get it from your Supabase Dashboard: Settings > API > Project API keys > anon (public)
SUPABASE_URL = "https://fdujrbmufqmpfisscclk.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZkdWpyYm11ZnFtcGZpc3NjY2xrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY4MzQ1OTAsImV4cCI6MjA3MjQxMDU5MH0.WMlrlIx-IkYW2mbdg1fa_oLwk2k-SrKu5e6L1cuZ0NQ" # Paste your anon key here

# Your user's credentials
USER_EMAIL = "sseaditya@gmail.com"
USER_PASSWORD = "analysedrive" # Paste the user's password here

# --- Script to sign in and get the token ---
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    response = supabase.auth.sign_in_with_password({
        "email": USER_EMAIL,
        "password": USER_PASSWORD
    })
    
    access_token = response.session.access_token
    print("\n✅ Login Successful!")
    print("\n🔑 Your JWT Access Token is:\n")
    print(access_token)
    print("\nCopy the token above and use it in Postman.\n")

except Exception as e:
    print(f"\n❌ Login Failed: {e}")