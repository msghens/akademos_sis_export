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
ethosBaseURL = os.environ["ETHOSBASEURL"]
ethosAppAPIKey = os.environ["MSGETHOSDEVAPIKEY"]

# Initialize the Ethos API client and obtain a login session using the API key
ethosClient = EllucianEthosPythonClient.EllucianEthosAPIClient(baseURL=ethosBaseURL)
loginSession = ethosClient.getLoginSessionFromAPIKey(apiKey=ethosAppAPIKey)




def get_start_date() -> str:
    """
    Calculates the date exactly six months prior to the current date 
    and returns it in the required ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ).
    
    The time component is explicitly set to 00:00:00 UTC on the calculated date.
    """
    # Use the current moment in UTC for calculation
    current_utc_time = datetime.datetime.now(datetime.timezone.utc)
    
    # Subtract exactly 6 calendar months using relativedelta
    date_six_months_ago = current_utc_time - relativedelta(months=6)
    
    # Normalize the time to midnight (00:00:00) UTC
    # This discards any current hours, minutes, etc.
    start_of_day_utc = date_six_months_ago.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Format the date string as YYYY-MM-DDTHH:MM:SS and manually append 'Z'
    return start_of_day_utc.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'

def get_end_date() -> str:
    """
    Calculates the date exactly two  months later to the current date 
    and returns it in the required ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ).
    
    The time component is explicitly set to 00:00:00 UTC on the calculated date.
    """
    # Use the current moment in UTC for calculation
    current_utc_time = datetime.datetime.now(datetime.timezone.utc)
    
    # Subtract exactly 6 calendar months using relativedelta
    date_six_months_ago = current_utc_time + relativedelta(months=2)
    
    # Normalize the time to midnight (00:00:00) UTC
    # This discards any current hours, minutes, etc.
    start_of_day_utc = date_six_months_ago.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Format the date string as YYYY-MM-DDTHH:MM:SS and manually append 'Z'
    return start_of_day_utc.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'

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



def find_greater(a: Optional[Union[int, float]], 
                  b: Optional[Union[int, float]]) -> Optional[Union[int, float]]:
    """
    Compares two inputs (which can be numbers or None) and returns the 
    greater numerical value.

    Args:
        a: The first number (or None).
        b: The second number (or None).

    Returns:
        The greater number if both are valid, the single number if one is None,
        or None if both are None.
    """
    
    # 1. Check if both are None
    if a is None and b is None:
        return None
        
    # 2. Check if only 'a' is None
    if a is None:
        # Since 'b' must be a number (checked in step 1), we return b.
        return b
        
    # 3. Check if only 'b' is None
    if b is None:
        # Since 'a' must be a number, we return a.
        return a
        
    # 4. Both are guaranteed to be valid numbers (int or float)
    # Use the built-in max() function for the final comparison.
    return max(a, b)


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


# Helper functions to get course and subject details
# TODO: These could be optimized with caching if we find that we are making repeated calls for the same course or subject IDs. For now, we will keep it simple and make direct API calls.
def get_course(course_id: str)-> dict:
    if course_id in courseCache:
        return courseCache[course_id]
    course = ethosClient.getResource(
        loginSession=loginSession,
        resourceName="courses",
        version=None,
        resourceID=course_id
    )
    if course:
        result = course.dict
        courseCache[course_id] = result
        return result if result is not None else {}
    return {}

# Helper function to get subject details
# TODO: These could be optimized with caching if we find that we are making repeated calls for the same course or subject IDs. For now, we will keep it simple and make direct API calls.
def get_subject(subject_id: str)-> dict:
    if subject_id in subjectCache:
        return subjectCache[subject_id]
    subject = ethosClient.getResource(
        loginSession=loginSession,
        resourceName="subjects",
        version=None,
        resourceID=subject_id
    )
    if subject:
        result = subject.dict
        subjectCache[subject_id] = result
        return result if result is not None else {}
    return {}


print("Start")



params = {}
# We will use the start and end date to limit the number of terms we have to deal with for now. We can expand this later if needed.
# TODO: add starton and endon to the criteria to limit the number of terms we have to deal with for now. We can expand this later if needed.
# starton and endon throw an error when added to the criteria, so we will filter the terms after we get them back from the API. This is not ideal, but it works for now. We can revisit this later if needed.
startOn = get_start_date()
endOn = get_end_date()
params["criteria"] = '{"category":{"type":"term"}}'
# params["limit"] = 3
# params["offset"] = 0
academicPeriodIterator = ethosClient.getResourceIterator(
  loginSession=loginSession,
  resourceName="academic-periods",
  version=None,
  params=params,
  pageSize=100
)

#Get Terms
cur = 0
# Find terms within a 9 month window in the past and 9 month window in the future. This is to limit the number of terms we have to deal with for now. We can expand this later if needed.
terms = dict()
for period in academicPeriodIterator:
  cur += 1
  pprint(period.dict)
  
  period_dict = period.dict
  if period_dict is None:
    continue
  if check_date_range(period_dict['startOn'], period_dict['endOn']):
    # print("Term is within 9 months in the past and 9 months in the future")
    print(cur, "period", period.dict)
    print(f"{cur} period, Term: {period_dict['code']}, Startdate {period_dict['startOn']}, Enddate {period_dict['endOn']}, Registration {period_dict['registration']}")
    terms[period_dict['code']] = {"startOn": period_dict['startOn'], "endOn": period_dict['endOn'], "registration": period_dict['registration'], "id": period_dict['id'], "title": period_dict['title']}


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


#Pref for file writing
sections_list = []
number_of_sections = 0
for code, details in terms.items():
    
    params["criteria"] = "{\"academicPeriod\":{\"id\":\"" + details["id"] + "\"},\"status\":\"open\"}"
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
        number_of_sections += 1
        # print(sections_dict['course']['id'])
        # pprint(sections_dict)
        course_dict = get_course(sections_dict['course']['id'])
        subject_dict = get_subject(course_dict['subject']['id'])
        # pprint(subject_dict)
        # pprint(course_dict)
        # pprint(course_dict['credits'])
        course_credit = find_greater(course_dict['credits'][0]['minimum'], course_dict['credits'][0]['maximum'])
        sections_list.append({
            "course_number": course_dict['number'],
            "course_title": course_dict['title'],
            "course_name": subject_dict['abbreviation'],
            "course_code": sections_dict['code'],
            "course_section": None,
            "course_credit": course_credit,
            "course_model": None, #to be coded later if needed
            "department_code":  subject_dict['abbreviation'],
            "department_desc": subject_dict['title'],
            "campus_code": "TBD", #to be coded later for man, online,etc
            "campus_desc": "TBD", #to be coded later
            "term_code": code,
            "term_desc": details["title"],
            "session_code": None, #to be coded later if needed,
            "start_date": sections_dict["startOn"].split('T')[0],
            "end_date": sections_dict["endOn"].split('T')[0],
            "enrollment_cap": sections_dict['maxEnrollment']           
        })
        print( sections_dict['guid'], "course_number:", course_dict['number'], "course_title:", course_dict['title'], "course_name:", subject_dict['abbreviation'], "course_code:", sections_dict['code'], "term_code:", code, "term_desc:", details["title"], "start_date:", sections_dict["startOn"].split('T')[0], "end_date:", sections_dict["endOn"].split('T')[0], "enrollment_cap:", sections_dict['maxEnrollment'])





try:
    final_path = create_csv_from_dict_list(sections_list, "course")
    print(f"Successfully created CSV at: {final_path}")
except ValueError as e:
    print(f"Error: {e}")  

print(f"Number of sections: {number_of_sections}")

# create user csv 
#start with instuctor first.
# create a list of instructors to be exported to a CSV
instructors_list = []
for code, details in terms.items():
    params["criteria"] = "{\"academicPeriod\":{\"id\":\"" + details["id"] + "\"},\"status\":\"open\"}"
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
        # Get section instructors
        params["criteria"] = "{\"section\": {\"id\": \"" + sections_dict['guid'] + "\"}}"
        instructorIterator = ethosClient.getResourceIterator(
            loginSession=loginSession,
            resourceName="section-instructors",
            version="10",
            params=params
        )
        for instructor in instructorIterator:
            personResourceID = instructor.dict.get('instructor', {}).get('id')
            if personResourceID:
                person = ethosClient.getResource(
                    loginSession=loginSession,
                    resourceName="persons",
                    resourceID=personResourceID,
                    version=None
                )
                if person:
                    instructors_list.append({
                        "instructor_id": personResourceID,
                        "instructor_name": person.dict["names"][0]["fullName"],
                        "term_code": code,
                        "term_desc": details["title"]
                    })

try:
    final_path = create_csv_from_dict_list(instructors_list, "instructors")
    print(f"Successfully created CSV at: {final_path}")
except ValueError as e:
    print(f"Error: {e}")

for  instructor in instructors_list:
    print(instructor)


print("End")