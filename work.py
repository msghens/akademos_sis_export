import sys
import os
from pprint import pprint
from dotenv import load_dotenv
from pathlib import Path
import csv
import datetime
from typing import List, Dict, Any,Union,Optional
import datetime
from dateutil import parser
from dateutil.relativedelta import relativedelta


# This sample uses a resource iterator to list all the academic periods

import EllucianEthosPythonClient
load_dotenv()

# Global variables
courseCache = {}
subjectCache = {}


# Global variables for Ethos API access
ethosBaseURL = os.environ.get("ETHOSBASEURL")
ethosAppAPIKey = os.environ.get("MSGETHOSDEVAPIKEY")

if not ethosBaseURL or not ethosAppAPIKey:
    print("Error: Missing ETHOSBASEURL or MSGETHOSDEVAPIKEY environment variable.")
    sys.exit(1)

# Initialize the Ethos API client and obtain a login session using the API key
ethosClient = EllucianEthosPythonClient.EllucianEthosAPIClient(baseURL=ethosBaseURL)
try:
    loginSession = ethosClient.getLoginSessionFromAPIKey(apiKey=ethosAppAPIKey)
except Exception as e:
    print(f"Error obtaining login session: {e}")
    sys.exit(1)

params = {}
params["criteria"] = '{"category":{"type":"term"}}'
academicPeriodIterator = ethosClient.getResourceIterator(
  loginSession=loginSession,
  resourceName="academic-periods",
  version=None,
  params=params,
  pageSize=25
)

exampleURL = "/api/ca-class-roster?ssbsectTermCodet=202650&ssbsectCrnt=51232"
exampleVersion = "1"

def sampleInjectHeaderFunctionForGet(headers):
  headers["Accept"] = "application/vnd.hedtech.integration.v1.0.0+json"
result = ethosClient.sendGetRequest(
  url=exampleURL,
  loginSession=loginSession,
  injectHeadersFn=sampleInjectHeaderFunctionForGet
)

# print(result.status_code)
# print(result.content)

# classRoster = result.json()
# print(classRoster)


import EllucianEthosPythonClient

# Configuration - replace with your values
ETHOS_BASE_URL = ethosBaseURL # No trailing slash
ETHOS_API_KEY = ethosAppAPIKey
SECTION_GUID = "42fb2a3b-4abf-47b7-b9f6-2ffccc992cab"  # Or query by CRN/term

# Create client and login session
client = EllucianEthosPythonClient.EllucianEthosAPIClient(baseURL=ETHOS_BASE_URL)
login_session = client.getLoginSessionFromAPIKey(apiKey=ETHOS_API_KEY)

# Option A: Get full section details (includes instructor info in many cases)
section = client.getResource(
    loginSession=login_session,
    resourceName="sections",
    resourceID=SECTION_GUID,
    version="16"  # Common version for sections
)

if section:
    print(section.dict)  # Inspect the full JSON structure
    # Look for keys like 'instructors', 'sectionInstructors', etc.
    instructors = section.dict.get('instructors') or section.dict.get('sectionInstructors')
    print("Instructors:", instructors)

params["criteria"]='{"section": {"id": "42fb2a3b-4abf-47b7-b9f6-2ffccc992cab"}}'
instructor_iterator = client.getResourceIterator(
    loginSession=login_session,
    resourceName="section-instructors",
    params=params,
    version="10"
)

for instr in instructor_iterator:
    print(instr.dict)
    # Typically includes person reference, primary flag, workload, etc.    
    personResourceID = instr.dict.get('instructor', {}).get('id')


person = ethosClient.getResource(
  loginSession=loginSession,
  resourceName="persons",
  resourceID=personResourceID,
  version=None
)
print("Found:", person.dict["names"][0]["fullName"])