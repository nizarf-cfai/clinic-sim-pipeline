from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
import datetime
import bucket_ops
import json
import schedule_manager

app = FastAPI(title="Clinic Agent Backend")
gcs = bucket_ops.GCSBucketManager(bucket_name="clinic_sim")

# ==========================================
# 1. DATA MODELS (Matching your Dialogflow Parameters)
# ==========================================

class PatientRegistrationRequest(BaseModel):
    # We use Optional for fields that might be missing, 
    # though your agent tries to collect them all.
    first_name: str
    last_name: str
    dob: str
    gender: str
    occupation: Optional[str] = None
    marital_status: Optional[str] = None
    phone: str
    email: str
    address: Optional[str] = None
    
    # Emergency Contact
    emergency_name: Optional[str] = None
    emergency_relation: Optional[str] = None
    emergency_phone: Optional[str] = None
    
    # Medical Data
    chief_complaint: str
    medical_history: Optional[str] = "None"
    allergies: Optional[str] = "None"

class RegistrationResponse(BaseModel):
    patient_id: str
    status: str

class SlotResponse(BaseModel):
    available_slots: List[str]

# ==========================================
# 2. ENDPOINTS (Matching your Tool Schema)
# ==========================================

@app.post("/register", response_model=RegistrationResponse)
async def register_patient(patient: PatientRegistrationRequest):
    """
    Receives patient data, 'saves' it to a database, and returns an ID.
    """
    print(f"--- Receiving Registration Request for {patient.first_name} {patient.last_name} ---")
    print(f"Complaint: {patient.chief_complaint}")
    
    # SIMULATION: Here you would write code to save to SQL/Firebase/Postgres
    # For now, we generate a fake Patient ID
    patient_data = patient.dict()
    patient_id = f"PT-{str(uuid.uuid4())[:8].upper()}"
    patient_data["patient_id"] = patient_id

    file_path = f"patient_data/{patient_id}/patient_form.json"
        
    # Convert to JSON string
    json_content = json.dumps(patient_data, indent=4)
    
    # Overwrite the file in GCS using the agent's bucket manager
    gcs.create_file_from_string(
        json_content, 
        file_path, 
        content_type="application/json"
    )
    # Return the response Dialogflow expects
    return {
        "patient_id": patient_id,
        "status": "Patient profile created successfully."
    }

@app.get("/slots", response_model=SlotResponse)
async def get_available_slots(doctor_type: Optional[str] = "General"):
    """
    Returns a list of available appointment slots.
    """
    print(f"--- Checking slots for doctor type: {doctor_type} ---")
    
    # SIMULATION: logic to get dates relative to 'today'

    schedule_ops = schedule_manager.ScheduleCSVManager(gcs_manager=gcs, csv_blob_path=f"clinic_data/doctor_schedule.csv")
    return schedule_ops.get_empty_schedule()


# ==========================================
# 3. HOW TO RUN
# ==========================================
# Run via terminal: uvicorn main:app --reload