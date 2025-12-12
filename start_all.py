import subprocess
import time
import os
import signal
import sys

def start_services():
    print("🚀 Starting Futu MCP Services...")

    # Start Backend
    print("Starting Backend (start_new.py)...")
    backend = subprocess.Popen([sys.executable, "start_new.py"])
    
    # Start Frontend
    print("Starting Frontend (npm run dev)...")
    frontend = subprocess.Popen(
        ["npm", "run", "dev"], 
        cwd="web/dashboard-app",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    print("\n✅ Services started!")
    print("Backend running on port 8000 (proxied from frontend)")
    print("Frontend running at: http://localhost:5173/")
    print("\nPress Ctrl+C to stop all services.")

    try:
        while True:
            time.sleep(1)
            if backend.poll() is not None:
                print("❌ Backend process exited unexpectedly.")
                break
            if frontend.poll() is not None:
                print("❌ Frontend process exited unexpectedly.")
                break
    except KeyboardInterrupt:
        print("\n🛑 Stopping services...")
        backend.terminate()
        frontend.terminate()
        print("✅ Services stopped.")

if __name__ == "__main__":
    start_services()
