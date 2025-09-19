import time
import uvicorn
from concurrent.futures import ThreadPoolExecutor

def run_auth():
    uvicorn.run("auth_service.app.main:app", host="0.0.0.0", port=8001)  # no reload

def run_facility():
    uvicorn.run("facility_service.app.main:app", host="0.0.0.0", port=8002)  # no reload

if __name__ == "__main__":
    with ThreadPoolExecutor() as executor:
        executor.submit(run_auth)
        executor.submit(run_facility)
        
        print("✅ Both services started: auth_service(8001), facility_service(8002)")
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping services...")
