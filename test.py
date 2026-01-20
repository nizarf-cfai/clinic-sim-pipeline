import my_agents
import asyncio
import json
import bucket_ops

input_criteria = {
    "patient_id" : "P0001",
    "target_condition": "Decompensated Alcoholic Liver Disease (Cirrhosis) with Ascites",
    "acuity": "Urgent / Hospital Admission Required",
    "demographics": {
        "age": 54,
        "sex": "Male",
        "location": "Manchester, United Kingdom",
        "occupation": "Former Bricklayer (currently unemployed due to health)",
        "origin_context": "UK Working Class"
    },
    "presenting_symptoms": [
        "Significant abdominal swelling (looks '9 months pregnant')",
        "Yellowing of eyes and skin (Jaundice)",
        "Intermittent confusion and forgetfulness (Hepatic Encephalopathy)",
        "Swollen ankles (Peripheral Edema)"
    ],
    "medical_history_context": {
        "chronic_conditions": [
            "Alcoholic Liver Cirrhosis (Child-Pugh Score B)", 
            "Esophageal Varices (banded 2 years ago)", 
            "Depression"
        ],
        "substance_history": "Heavy alcohol consumer (approx. 60 units/week) for 20 years. Claims to have cut down recently but relapsed last week.",
        "medication_compliance": "Poor. Often forgets his Lactulose."
    },
    "personality_profile": {
        "emotional_state": "Defensive about his drinking, but physically uncomfortable and scared. Slightly confused/slow to answer due to encephalopathy.",
        "attitude": "Stoic but clearly suffering. Uses UK slang (e.g., 'feeling rubbish', 'bloody swollen').",
        "health_literacy": "Low. Understands his liver is 'dodgy' but doesn't grasp the concept of liver failure."
    },
    "clinical_directives_hint": {
        "labs_focus": "Must show Deranged Liver Function (High Bilirubin, Low Albumin) and Coagulopathy (High INR).",
        "physical_focus": "Positive shifting dullness (Ascites), Spider Naevi on chest."
    },
    "encounters_count" : 3,
    "imaging_count_in_encounters" : 2
}


PM = my_agents.PatientManager(input_criteria)
gcs = bucket_ops.GCSBucketManager(bucket_name="clinic_sim")
# print("Generating Patient Profile...")
# patient_profile = asyncio.run(PM.generate_patient_profile())
# print("Generating System Prompt...")
# system_prompt = asyncio.run(PM.generate_system_prompt(patient_profile))
# print("Generating Encounters...")
# encounters = asyncio.run(PM.generate_encounters(patient_profile))
# print("Generating Labs...")
# labs = asyncio.run(PM.generate_labs(patient_profile, encounters))


# asyncio.run(PM.generate_ground_truth())
asyncio.run(PM.generate_pre_consultation_chat())

with open("output/P0001/encounters.json", "r", encoding="utf-8") as f:
    encounters = json.load(f)


with open("output/P0001/labs.json", "r", encoding="utf-8") as f:
    labs = json.load(f)

with open("output/P0001/patient_profile.txt", "r", encoding="utf-8") as f:
    patient_profile = f.read()

with open("output/P0001/lab1.json", "r", encoding="utf-8") as f:
    lab1 = json.load(f)


# "gs://clinic_sim/patient_data/P0001/encounters.json"

# imaging_img = asyncio.run(PM.generate_imaging_report_img(encounters[1]))

# lab_doc = asyncio.run(PM.lab_doc_parser(lab1, "Arthur Pendelton"))

# lab_image = asyncio.run(PM.generate_lab_img(lab_doc, "Arthur Pendelton"))

# print("Generating Encounter Images...")
# images = asyncio.run(PM.generate_encounter_img(encounters[0]))


# gcs.create_file_from_string(json.dumps(encounters), "data/config.json", content_type="application/json")
# gcs.create_file_from_string(patient_profile, "patient_profile.txt")