
# MedForce API Usage Guide

**Base URL:**
```
https://clinic-sim-pipeline-481780815788.europe-west1.run.app
```

This guide details how to interact with the Patient Generation, Image Retrieval, and Schedule Management endpoints using Python.

---

## 1. Generate Synthetic Patient
Creates a new patient profile, history, and medical records based on a natural language clinical seed description.

*   **Endpoint:** `/generate/patient`
*   **Method:** `POST`

### Request Body Schema
| Field | Type | Description |
| :--- | :--- | :--- |
| `description` | string | A detailed clinical narrative describing the patient's symptoms, labs, and history. |
| `encounters_count` | integer | The number of historical medical encounters to generate. |
| `imaging_count_in_encounters` | integer | How many of those encounters should include imaging reports. |

### Python Example
```python
import requests
import json

BASE_URL = "https://clinic-sim-pipeline-481780815788.europe-west1.run.app"
endpoint = f"{BASE_URL}/generate/patient"

# Define the clinical seed
patient_seed = {
    "description": "A 44-year-old male presents with profound malaise and a dull, aching sensation localized to the right upper quadrant of the abdomen. Clinical examination reveals mild scleral icterus and a noticeable distension of the abdominal cavity. The patient reports a sudden onset of dark, tea-colored urine and pale, clay-colored stools over the past week. Serum analysis indicates a significant elevation in hepatic transaminases, with ALT and AST levels exceeding ten times the upper limit of normal.",
    "encounters_count": 5,
    "imaging_count_in_encounters": 2
}

print(f"--- Generating Patient ---")
response = requests.post(endpoint, json=patient_seed)

if response.status_code == 200:
    data = response.json()
    print("✅ Patient Generated Successfully")
    print(json.dumps(data, indent=2))
else:
    print(f"❌ Error {response.status_code}: {response.text}")
```

---

## 2. Retrieve & Display Medical Image
Fetches a specific file (image/pdf) from a patient's raw data storage and displays it (useful for Jupyter Notebooks).

*   **Endpoint:** `/image/{patient_id}/{filename}`
*   **Method:** `GET`
*   **Response:** Direct binary stream of the image (MIME type `image/png`, `image/jpeg`, etc.).

### Python Example (Jupyter Notebook)
```python
import requests
from IPython.display import Image, display

BASE_URL = "https://clinic-sim-pipeline-481780815788.europe-west1.run.app"

# Parameters
PATIENT_ID = "P0001"
# Ensure the filename matches exactly what is stored in the bucket
FILENAME = "patient_data_P0001_raw_data_encounter_report_0_2026-01-19.png"

url = f"{BASE_URL}/image/{PATIENT_ID}/{FILENAME}"

print(f"Requesting: {url}")
response = requests.get(url)

# Check and Display
if response.status_code == 200:
    print("✅ Success! Displaying image:")
    # Render the raw bytes directly
    display(Image(data=response.content))
else:
    print(f"❌ Error {response.status_code}: {response.text}")
```

---

## 3. Switch Schedule Slots
Swaps the contents (Patient and Status) of two specific time slots in a clinician's schedule. This is useful for rescheduling or moving appointments.

*   **Endpoint:** `/schedule/switch_slots`
*   **Method:** `POST`

### Request Body Schema
| Field | Type | Description |
| :--- | :--- | :--- |
| `clinician_id` | string | The ID of the Nurse (N...) or Doctor (D...). |
| `item1` | object | The **first** time slot (Date/Time) to swap. |
| `item2` | object | The **second** time slot (Date/Time) to swap. |

> **Note:** The `patient` field inside `item1` and `item2` is optional for finding the slot (Date and Time are the keys), but the object structure usually requires the field to exist.

### Python Example
```python
import requests

BASE_URL = "https://clinic-sim-pipeline-481780815788.europe-west1.run.app"
endpoint = f"{BASE_URL}/schedule/switch_slots"

payload = {
    "clinician_id": "N0001",
    # Slot A: 13:30 on Jan 22
    "item1" : {
        "date": "2026-01-22",
        "time": "13:30",
        "patient": "" # Optional, serves as placeholder
    },
    # Slot B: 14:00 on Jan 22
    "item2" : {
        "date": "2026-01-22",
        "time": "14:00",
        "patient": "" # Optional, serves as placeholder
    }
}

print(f"--- Switching Slots ---")
response = requests.post(endpoint, json=payload)

if response.status_code == 200:
    data = response.json()
    print("✅ Schedule Swapped Successfully")
    print(data)
else:
    print(f"❌ Error {response.status_code}: {response.text}")
```