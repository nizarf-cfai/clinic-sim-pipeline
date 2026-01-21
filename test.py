import my_agents
import asyncio
import json
import bucket_ops
import requests
input_criteria = {
    "patient_id": "P0002",
    "target_condition": "Non-Alcoholic Steatohepatitis (NASH)-Related Cirrhosis with Portal Hypertension",
    "acuity": "Semi-Urgent / Specialist Hepatology Review Required",
    "demographics": {
    "age": 62,
    "sex": "Female",
    "location": "Leeds, United Kingdom",
    "occupation": "Retired School Administrator",
    "origin_context": "UK Middle Class"
    },
    "presenting_symptoms": [
    "Progressive abdominal bloating",
    "Increasing fatigue and reduced exercise tolerance",
    "Easy bruising",
    "Mild shortness of breath when lying flat"
    ],
    "medical_history_context": {
    "chronic_conditions": [
    "NASH-related Liver Cirrhosis (Child-Pugh Score A progressing to B)",
    "Type 2 Diabetes Mellitus",
    "Hypertension",
    "Hyperlipidaemia"
    ],
    "substance_history": "Minimal alcohol intake (1–2 units/week). No history of substance misuse.",
    "medication_compliance": "Generally good, but occasionally misses diuretics due to urinary frequency."
    },
    "personality_profile": {
    "emotional_state": "Anxious and worried about disease progression after being told her liver is 'scarred'.",
    "attitude": "Polite, cooperative, and detail-oriented. Asks many questions about prognosis.",
    "health_literacy": "Moderate. Understands metabolic disease but struggles to link diabetes and obesity to liver failure."
    },
    "clinical_directives_hint": {
    "labs_focus": "Mildly elevated ALT/AST, thrombocytopenia, borderline INR, reduced albumin.",
    "physical_focus": "Splenomegaly, mild ascites, palmar erythema."
    },
    "encounters_count": 4,
    "imaging_count_in_encounters": 3
}



PM = my_agents.PatientManager(input_criteria)
gcs = bucket_ops.GCSBucketManager(bucket_name="clinic_sim")
img_proc = my_agents.RawDataProcessing()

# result = asyncio.run(img_proc.get_text_doc("patient_data/P0002/encounter_report_0_2026-01-19.png"))
# print(result)
# with open("result_test.json", "w", encoding="utf-8") as f:
#     json.dump(result, f)



BASE_URL = "http://localhost:8000"
PATIENT_ID = "P0001"  # <--- REPLACE THIS with an actual ID from your generation step

endpoint = f"{BASE_URL}/process/{PATIENT_ID}/preconsult"
response = requests.get(endpoint)

print("Status Code:", response.status_code)
print("Response JSON:", response.json())

# print("Generating Patient Profile...")
# patient_profile = asyncio.run(PM.generate_patient_profile())
# print("Generating System Prompt...")
# system_prompt = asyncio.run(PM.generate_system_prompt(patient_profile))
# print("Generating Encounters...")
# encounters = asyncio.run(PM.generate_encounters(patient_profile))
# print("Generating Labs...")
# labs = asyncio.run(PM.generate_labs(patient_profile, encounters))


# asyncio.run(PM.generate_ground_truth())
# asyncio.run(PM.generate_pre_consultation_chat())

# with open("output/P0001/encounters.json", "r", encoding="utf-8") as f:
#     encounters = json.load(f)


# with open("output/P0001/labs.json", "r", encoding="utf-8") as f:
#     labs = json.load(f)

# with open("output/P0001/patient_profile.txt", "r", encoding="utf-8") as f:
#     patient_profile = f.read()

# with open("output/P0001/lab1.json", "r", encoding="utf-8") as f:
#     lab1 = json.load(f)


# patient_profile = gcs.read_file_as_string("patient_data/P0002/patient_profile.txt")
# asyncio.run(PM.generate_referral_letter())
# "gs://clinic_sim/patient_data/P0001/encounters.json"

# imaging_img = asyncio.run(PM.generate_imaging_report_img(encounters[1]))

# lab_doc = asyncio.run(PM.lab_doc_parser(lab1, "Arthur Pendelton"))

# lab_image = asyncio.run(PM.generate_lab_img(lab_doc, "Arthur Pendelton"))

# print("Generating Encounter Images...")
# images = asyncio.run(PM.generate_encounter_img(encounters[0]))


# gcs.create_file_from_string(json.dumps(encounters), "data/config.json", content_type="application/json")
# gcs.create_file_from_string(patient_profile, "patient_profile.txt")