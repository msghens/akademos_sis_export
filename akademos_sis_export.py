import sys
import os
from pprint import pprint
from dotenv import load_dotenv
from pathlib import Path
import csv
import datetime
from typing import List, Dict, Any,Union
import datetime
from dateutil import parser
from dateutil.relativedelta import relativedelta


# This sample uses a resource iterator to list all the academic periods

import EllucianEthosPythonClient
load_dotenv()

ethosBaseURL = os.environ["ETHOSBASEURL"]
ethosAppAPIKey = os.environ["MSGETHOSDEVAPIKEY"]


ethosClient = EllucianEthosPythonClient.EllucianEthosAPIClient(baseURL=ethosBaseURL)
loginSession = ethosClient.getLoginSessionFromAPIKey(apiKey=ethosAppAPIKey)


def create_csv_from_dict_list(data_list: List[Dict[str, Any]], file_prefix: str) -> Path:
    """
    Writes a list of dictionaries to a timestamped CSV file within the 'data' subdirectory.

    Args:
        data_list: A list of dictionaries, where each dictionary represents a row.
        file_prefix: The base name prefix for the file (e.g., 'user_data').

    Returns:
        The Path object pointing to the newly created CSV file.

    Raises:
        ValueError: If the data_list is empty or inconsistent.
    """
    
    # --- 1. Input Validation and Data Extraction ---
    if not data_list:
        raise ValueError("Input data_list cannot be empty.")
        
    # Determine headers (keys) based on the keys of the first dictionary
    # Assumes all dictionaries have the same keys for consistency
    fieldnames = list(data_list[0].keys())

    # --- 2. Path and Filename Generation ---
    # Get the current time and format it as YYYYMMDDHHSS
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Construct the final filename: file_YYYYMMDDHHSS.csv
    filename = f"{file_prefix}_{timestamp}.csv"
    
    # Use pathlib for robust path management
    output_dir = Path("data")
    output_file_path = output_dir / filename

    # Ensure the directory exists
    try:
        # parents=True allows creation of intermediate directories if they don't exist
        # exist_ok=True prevents an error if the directory already exists
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Error creating directory 'data': {e}")
        raise

    # --- 3. Writing the CSV File ---
    try:
        # Use 'w' mode to write/overwrite the file
        with open(output_file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # Write the header row
            writer.writeheader()
            
            # Write the data rows
            writer.writerows(data_list)
        
        return output_file_path
        
    except Exception as e:
        print(f"An error occurred while writing the CSV file: {e}")
        raise

# --- Example Usage (Mock data) ---
# mock_data = [
#     {'id': 1, 'name': 'Alice', 'score': 95.5},
#     {'id': 2, 'name': 'Bob', 'score': 88.0},
#     {'id': 3, 'name': 'Charlie', 'score': 79.2}
# ]
# try:
#     final_path = create_csv_from_dict_list(mock_data, "user_scores")
#     print(f"Successfully created CSV at: {final_path}")
# except ValueError as e:
#     print(f"Error: {e}")
# except Exception as e:
#     print(f"Process failed: {e}")




def check_date_range(begin_date_str: str, end_date_str: str) -> bool:
    """
    Checks if a date range falls within 9 months in the past and 9 months in the future
    relative to the moment of execution.

    Args:
        begin_date_str: The starting date of the period (ISO format).
        end_date_str: The ending date of the period (ISO format).

    Returns:
        True if the entire period is contained within the allowed window, False otherwise.
    """
    # 1. Establish the current reference point in UTC.
    # Using datetime.timezone.utc ensures consistency regardless of the server's timezone.
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
    except ValueError:
        # Fallback for environments where system timezone is required
        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

    # 2. Calculate constraints
    max_allowed_date = now + relativedelta(months=+9)
    min_allowed_date = now - relativedelta(months=9)

    # 3. Parse and normalize input dates
    try:
        # dateutil.parser handles ISO formats robustly.
        begin_date = parser.parse(begin_date_str)
        end_date = parser.parse(end_date_str)
    except Exception as e:
        print(f"Error parsing dates: {e}")
        return False

    # Crucial Step: Ensure timezone awareness for accurate comparison.
    # If the parsed dates are naive, assume UTC as per best practice for backend data.
    if begin_date.tzinfo is None and end_date.tzinfo is None:
        print("Warning: Input dates were naive. Assuming UTC timezone for comparison.")
        begin_date = begin_date.replace(tzinfo=datetime.timezone.utc)
        end_date = end_date.replace(tzinfo=datetime.timezone.utc)

    # 4. Determine the effective period bounds (handles swapped input order)
    period_start = min(begin_date, end_date)
    period_end = max(begin_date, end_date)

    # 5. Validation Check: [Start >= 9 months ago] AND [End <= 9 months from now]
    is_start_valid = period_start >= min_allowed_date
    is_end_valid = period_end <= max_allowed_date

    return is_start_valid and is_end_valid

print("Start")

# def isYes(str):
#   pro = userInput.strip().upper()
#   if len(pro)<1:
    # return False
#   return pro[0]=="Y"

params = {}
# userInput = input("Do you want to restrict to periods with open registration? (Y/N)")

# if isYes(userInput):
#   print("Restricting results where registration is open")
#   params["criteria"] = "{\"registration\":\"open\"}"
  

params["criteria"] = "{\"category\":{\"type\":\"term\"}}"
# params["limit"] = 3
# params["offset"] = 0
academicPeriodIterator = ethosClient.getResourceIterator(
  loginSession=loginSession,
  resourceName="academic-periods",
  version=None,
  params=params,
  pageSize=25
)



#Get Terms
cur = 0
# Find terms within a 9 month window in the past and 9 month window in the future. This is to limit the number of terms we have to deal with for now. We can expand this later if needed.
terms = dict()
for period in academicPeriodIterator:
  cur += 1
  # pprint(period.dict)
  
  period_dict = period.dict
  if period_dict is None:
    continue
  if check_date_range(period_dict['startOn'], period_dict['endOn']):
    # print("Term is within 9 months in the past and 9 months in the future")
    print(cur, "period", period.dict)
    print(f"{cur} period, Term: {period_dict['code']}, Startdate {period_dict['startOn']}, Enddate {period_dict['endOn']}, Registration {period_dict['registration']}")
    terms[period_dict['code']] = {"startOn": period_dict['startOn'], "endOn": period_dict['endOn'], "registration": period_dict['registration']}


# prep terms for csv export
term_list = []  
for code, details in terms.items():
    term_list.append({
        "term_code": code,
        "start_date": details["startOn"].split('T')[0],
        "end_date": details["endOn"].split('T')[0]
    })
# sort term list by start date
term_list.sort(key=lambda x: x["start_date"]) 
try:
    final_path = create_csv_from_dict_list(term_list, "terms")
    print(f"Successfully created CSV at: {final_path}")
except ValueError as e:
    print(f"Error: {e}")  



# Create Course file

# coursesIterator = ethosClient.getResourceIterator(
#   loginSession=loginSession,
#   resourceName="courses",
#   version=None,
#   params=None,
#   pageSize=100
# )



params["criteria"] = "{\"academicPeriod\":{\"id\":\"e3a4dc20-77d0-4727-a438-5147b6cb23d2\"}}"
sectionsIterator = ethosClient.getResourceIterator(
  loginSession=loginSession,
  resourceName="sections",
  version=None,
  params=params,
  pageSize=100
)



for sections in sectionsIterator:
  sections_dict = sections.dict
  if sections_dict is None:
    continue
  print(sections_dict)

print("End")