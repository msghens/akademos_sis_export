import csv
import datetime
import logging
import logging.handlers
import os
import socket
import statistics
import sys
import time
from pathlib import Path
from pprint import pprint
from typing import Any, Dict, List, Optional, Union

import EllucianEthosPythonClient
import paramiko
from dateutil import parser
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

### Akademos SIS Export


# Load environment variables from a .env file if it exists
load_dotenv()

# TODO: 
# - Add error handling and logging
# - Download all courses by Administrative Period 
# NOTES:
# - Email use username maildomain or fine sbcc -Akademos Wants college emails

# ====================== LOGGING SETUP ======================
def setup_logging():
    """Configure logging to both console and rotating file."""
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "akademos_sis_export.log"

    # Get log level from environment variable (default: INFO)
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper().strip()
    # Map string levels to logging constants
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    log_level = level_map.get(log_level_str, logging.INFO)

    # Create logger
    logger = logging.getLogger("akademos_sis")
    logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    if logger.hasHandlers():
        logger.handlers.clear()

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console Handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating File Handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,   # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# Initialize logger
logger = setup_logging()

# Start timer
start_time = time.monotonic()
logger.info("Starting Akademos SIS Export...")

# Global variables

# Cache for storing frequently accessed resources to avoid repeated API calls
# Global variables
courseCache: Dict[str, dict] = {}
subjectCache: Dict[str, dict] = {}
personCache: Dict[str, dict] = {}


# Global variables for Ethos API access
ethosBaseURL = os.environ["ETHOSBASEURL"]
ethosAppAPIKey = os.environ["MSGETHOSDEVAPIKEY"]

# Initialize the Ethos API client and obtain a login session using the API key
ethosClient = EllucianEthosPythonClient.EllucianEthosAPIClient(baseURL=ethosBaseURL)
loginSession = ethosClient.getLoginSessionFromAPIKey(apiKey=ethosAppAPIKey)


## Remove outliers using the Modified Z-Score method
def remove_outliers_modified_z(data, threshold=3.5):
    """
    Remove outliers using the Modified Z-Score method.
    
    Parameters:
        data (list): List of numeric values.
        threshold (float): Modified Z-score cutoff (default 3.5).
    
    Returns:
        list: Data without outliers.
    """
    if not data:
        return []

    # Ensure all elements are numeric
    try:
        data = [float(x) for x in data]
    except ValueError:
        logger.error("All elements in the data list must be numeric.", exc_info=True)
        raise ValueError("All elements must be numeric.")

    median_val = statistics.median(data)

    # Calculate Median Absolute Deviation (MAD)
    abs_devs = [abs(x - median_val) for x in data]
    mad = statistics.median(abs_devs)

    if mad == 0:
        return data  # No variation, so no outliers

    # Calculate Modified Z-Scores
    # Formula: MZ = 0.6745 * (x - median) / MAD
    modified_z_scores = [
        0.6745 * (x - median_val) / mad for x in data
    ]

    # Filter based on threshold
    filtered = [
        x for x, mz in zip(data, modified_z_scores)
        if abs(mz) <= threshold
    ]
    return filtered


def send_file_via_sftp(local_file_path: Path, remote_file_path: str) -> None:
    """
    Uploads a local file to a remote SFTP server with detailed debugging.
    """
    if not local_file_path.exists():
        logger.error(f"Local file not found: {local_file_path}")
        raise FileNotFoundError(f"Local file not found: {local_file_path}")

    # === Load Environment Variables ===
    sftp_server = os.getenv("SFTPSERVER")
    sftp_port = int(os.getenv("SFTPPORT", 22))
    sftp_username = os.getenv("SFTPUSERNAME")
    sftp_password = os.getenv("SFTPPASSWORD")

    logger.info(f"SFTP Config - Server: {sftp_server}, Port: {sftp_port}, User: {sftp_username}")

    if not all([sftp_server, sftp_username, sftp_password]):
        logger.error("Missing SFTP environment variables (SFTPSERVER, SFTPUSERNAME, SFTPPASSWORD)")
        raise ValueError("Missing SFTP environment variables (SFTP_SERVER, SFTP_USERNAME, SFTP_PASSWORD)")

    ssh_client: Optional[paramiko.SSHClient] = None
    sftp: Optional[paramiko.SFTPClient] = None

    try:
        logger.info(f"Connecting to {sftp_server}:{sftp_port} ...")

        # Test basic network connectivity first
        try:
            sock = socket.create_connection((sftp_server, sftp_port), timeout=10)
            sock.close()
            logger.info("Network connectivity OK")
        except Exception as sock_err:
            logger.error(f"Cannot reach server on port {sftp_port}: {sock_err}",exc_info=True)
            logger.error("   Check hostname, port, firewall, and VPN.",exc_info=True)
            raise

        # SSH Connection
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        ssh_client.connect(
            hostname=sftp_server,  # type: ignore
            port=sftp_port,
            username=sftp_username,
            password=sftp_password,
            timeout=15,
            banner_timeout=15,
            auth_timeout=15,
            allow_agent=False,
            look_for_keys=False
        )

        logger.info("SSH connection established")

        transport = ssh_client.get_transport()
        if not transport:
            raise ConnectionError("Failed to get transport")

        sftp = paramiko.SFTPClient.from_transport(transport)
        if not sftp:
            logger.error("Failed to create SFTP client")
            raise ConnectionError("Failed to create SFTP client")

        logger.info(f"Uploading {local_file_path.name} to {remote_file_path}...")
        sftp.put(str(local_file_path), remote_file_path)

        logger.info(f"Successfully uploaded {local_file_path.name}")

    except paramiko.AuthenticationException:
        logger.error("Authentication failed - Check username/password",exc_info=True)
        raise
    except paramiko.SSHException as e:
        logger.error(f"SSH Error: {e}",exc_info=True)
        raise
    except socket.timeout:
        logger.error("Connection timeout - Server unreachable or too slow",exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}",exc_info=True)
        raise
    finally:
        if sftp:
            try:
                sftp.close()
            except:
                pass
        if ssh_client:
            try:
                ssh_client.close()
            except:
                pass

def format_runtime(seconds: float) -> str:
    """
    Convert runtime in seconds to a human-readable string.
    Handles hours, minutes, seconds, and milliseconds.
    """
    if seconds < 0:
        return "Invalid runtime"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0:
        parts.append(f"{secs}s")
    if millis > 0 and hours == 0:  # Show ms only if runtime < 1h
        parts.append(f"{millis}ms")

    return " ".join(parts) if parts else "0s"

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
        logger.error(f"Error creating directory 'data': {e}",exc_info=True)
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
        logger.error(f"An error occurred while writing the CSV file: {e}",exc_info=True)
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
        logger.error(f"Error parsing dates: {e}",exc_info=True)
        return False

    # Crucial Step: Ensure timezone awareness for accurate comparison.
    # If the parsed dates are naive, assume UTC as per best practice for backend data.
    if begin_date.tzinfo is None and end_date.tzinfo is None:
        logger.warn("Warning: Input dates were naive. Assuming UTC timezone for comparison.")
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
        result = course.dict or {}
        courseCache[course_id] = result
        return result
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
        if result is None:
            result = {}
        subjectCache[subject_id] = result
        return result
    return {}


# Helper function to get person details
# Cache for storing person details to avoid repeated API calls
def get_person(person_id: str)-> dict:
    if person_id in personCache:
        return personCache[person_id]
    person = ethosClient.getResource(
        loginSession=loginSession,
        resourceName="persons",
        version=None,
        resourceID=person_id
    )
    if person:
        result = person.dict
        if result is not None:
            personCache[person_id] = result
        return result if result is not None else {}
    return {}

def get_banner_id(person: dict) -> str:
    for credential in person.get('credentials', []):
        if credential.get('type') == 'bannerId':
            return credential.get('value').strip()[:50]
    return None # type: ignore

def get_banner_username(person: dict) -> str:
    for credential in person.get('credentials', []):
        if credential.get('type') == 'bannerUserName':
            return credential.get('value').strip()[:50]
    return None # type: ignore

logger.info("Start")



params = {}
# We will use the start and end date to limit the number of terms we have to deal with for now. We can expand this later if needed.
# TODO: add starton and endon to the criteria to limit the number of terms we have to deal with for now. We can expand this later if needed.
# starton and endon throw an error when added to the criteria, so we will filter the terms after we get them back from the API. This is not ideal, but it works for now. We can revisit this later if needed.
# Hard code only open registration terms for now since those are the only ones we care about for the course export. We can expand this later if needed.
startOn = get_start_date()
endOn = get_end_date()
params["criteria"] = '{"category":{"type":"term"},"registration":"open"}'
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
# Find terms that are open for registration
logger.info(f"Fetching academic periods")
terms = dict()
for period in academicPeriodIterator:
  cur += 1
  period_dict = period.dict
  terms[period_dict['code']] = {"startOn": period_dict['startOn'], "endOn": period_dict['endOn'], "registration": period_dict['registration'], "id": period_dict['id'], "title": period_dict['title']} # type: ignore

# comment out the date range check for now since we are filtering by open registration terms and those are the only ones we care about for the course export. We can revisit this later if needed.
#   if period_dict is None:
#     continue
#   if check_date_range(period_dict['startOn'], period_dict['endOn']):
#     # print("Term is within 9 months in the past and 9 months in the future")
#     print(cur, "period", period.dict)
#     print(f"{cur} period, Term: {period_dict['code']}, Startdate {period_dict['startOn']}, Enddate {period_dict['endOn']}, Registration {period_dict['registration']}")
#     terms[period_dict['code']] = {"startOn": period_dict['startOn'], "endOn": period_dict['endOn'], "registration": period_dict['registration'], "id": period_dict['id'], "title": period_dict['title']}


# prep terms for csv export
term_list = []  
for code, details in terms.items():
    logger.debug(f"Term: {code}, Startdate {details['startOn']}, Enddate {details['endOn']}, Registration {details['registration']}")
    term_list.append({
        "term_code": code.strip()[:20],
        "start_date": details["startOn"].split('T')[0],
        "end_date": details["endOn"].split('T')[0]
    })
# sort term list by start date
term_list.sort(key=lambda x: x["start_date"]) 
try:
    final_path = create_csv_from_dict_list(term_list, "terms")
    terms_file_path = final_path
    logger.info(f"Successfully created CSV at: {terms_file_path}")
except ValueError as e:
    logger.error(f"Error: {e}",exc_info=True)  



#Pref for file writing
# Prepare a list to store all sections
sections_list = []
sections_raw_list = []
# Initialize a counter for the number of sections
number_of_sections = 0
logger.info(f"Fetching sections for each term")
for code, details in terms.items():
    
    term_code = code
    params["criteria"] = "{\"academicPeriod\":{\"id\":\"" + details["id"] + "\"},\"status\":\"open\"}"
    sectionsIterator = ethosClient.getResourceIterator(

    loginSession=loginSession,
    resourceName="sections",
    version=None,
    params=params,
    pageSize=500
    )
    for sections in sectionsIterator:
        if sections.dict is None:
            continue
        course_dict = get_course(sections.dict['course']['id'])
        if course_dict is None:
            continue
        # Filter out non-credit courses for now since credit courses are the only ones we care about for the course export. We can expand this later if needed.
        if "NC" in course_dict['number']:
            continue
        sections_raw = sections
        sections_dict = sections.dict
        if sections_dict is None:
            continue
        sections_raw.dict['term_code'] = term_code # type: ignore
        sections_raw_list.append(sections_raw)

        number_of_sections += 1
    
        subject_dict = get_subject(course_dict['subject']['id'])
        course_credit = find_greater(course_dict['credits'][0]['minimum'], course_dict['credits'][0]['maximum'])
        
        sections_list.append({
            "course_number": sections_dict['code'].strip()[:100],
            "course_title": sections_dict['title'].strip()[:100],
            "course_name": subject_dict['abbreviation'].strip()[:60],
            "course_code": course_dict['number'].strip()[:60],
            "course_section": sections_dict['number'].strip()[:60], #to be coded later if needed
            "course_credit": str(course_credit)[:3] if course_credit else "0",
            "course_model": None, #to be coded later if needed Designate courses in a particular program (e.g. EA). Required for Equitable Access clients
            "department_code":  subject_dict['abbreviation'].strip()[:20],
            "department_desc": subject_dict['title'].strip()[:150],
            "campus_code": None, #to be coded later for man, online,etc
            "campus_desc": None, #to be coded later
            "term_code": code.strip()[:20],
            "term_desc": terms[code]["title"].strip()[:150],
            "session_code": None, #to be coded later if needed
            "start_date": sections_dict["startOn"].split('T')[0],
            "end_date": sections_dict["endOn"].split('T')[0],
            "enrollment_cap": int(str(sections_dict['maxEnrollment'])[:4] if str(sections_dict['maxEnrollment']) else 0)
        })
        logger.debug(f"Section: {sections_dict['code']} - {sections_dict['title']} - Term: {code} - Startdate {sections_dict['startOn']} - Enddate {sections_dict['endOn']} - Enrollment Cap: {sections_dict['maxEnrollment']}")
        # Break if we've reached the limit. For testing purposes, we'll limit to 10 sections
        # if number_of_sections > 10:
        #     break
try:
    final_path = create_csv_from_dict_list(sections_list, "course")
    course_file_path = final_path
    logger.info(f"Successfully created CSV at: {final_path}")
except ValueError as e:
    logger.error(f"Error: {e}",exc_info=True)  

logger.info(f"Number of sections: {number_of_sections}")

# create user csv 
#start with instuctor first.
# create a list of instructors to be exported to a users CSV
user_list = []
# list of time.perf_counter() to measure the time taken for each person api call
person_times = []
personCounter = 0;
logger.info(f"Fetching instructors and students for each section")
for sections in sections_raw_list:
    sections_dict = sections.dict
    if sections_dict is None:
        continue
    course_dict = get_course(sections_dict['course']['id'])
    subject_dict = get_subject(course_dict['subject']['id'])    
    # Get section instructors
    params["criteria"] = "{\"section\": {\"id\": \"" + sections_dict['guid'] + "\"}}"
    instructorIterator = ethosClient.getResourceIterator(
        loginSession=loginSession,
        resourceName="section-instructors",
        version="10",
        params=params
    )
    
    # Process each instructor and add them to the user list
    duplicate_instructor_ids = set()  # To track already processed instructors for this section
    for instructor in instructorIterator:
        personResourceID = instructor.dict.get('instructor', {}).get('id') # type: ignore
        if personResourceID and personResourceID not in duplicate_instructor_ids:
            duplicate_instructor_ids.add(personResourceID)  # Mark this instructor as processed

            perf_counter_start = time.perf_counter()
            person = get_person(personResourceID)
            person_times.append(time.perf_counter() - perf_counter_start)
            if person:
                logger.debug(f"Processing enrollment for person ID: {personResourceID} PROFESSOR)")
                #Fix first name to have None instead of a '.'
                person['names'][0]['firstName']=person['names'][0]['firstName'].strip()[:150] # None create error for first name if it is a '.' so we will fix it here to have None instead of a '.'
                if person['names'][0]['firstName'].strip() == ".":
                    person['names'][0]['firstName'] = None
                user_list.append({
                    "id": get_banner_id(person),
                    "role": "professor",
                    "first_name": person['names'][0]['firstName'],
                    "last_name": person['names'][0]['lastName'].strip()[:150],
                    "email": get_banner_username(person) + "@pipeline.sbcc.edu",
                    "phone_number": None,
                    "address_line1": None,
                    "address_line_2": None,
                    "city": None,
                    "state": None,
                    "postal_code": None,
                    "student_major": None,
                    "student_grade_level": None,
                    "course_number": sections_dict['code'].strip()[:100],
                    "term_code": sections_dict['term_code'].strip()[:20],
                    "term_desc": terms[sections_dict['term_code']]["title"].strip()[:150],
                    "username": get_banner_username(person)
                })
                personCounter += 1
                logger.debug
    # Get section enrollments
    params["criteria"] = "{\"section\": {\"id\": \"" + sections_dict['guid'] + "\"}}"
    enrollmentIterator = ethosClient.getResourceIterator(
        loginSession=loginSession,
        resourceName="section-registrations",
        version="16",
        params=params
    )
    
    # Process each enrollment and add them to the user list
    duplicate_enrollment_ids = set()  # To track already processed enrollments for this section
    for enrollment in enrollmentIterator:
        enrollment_dict = enrollment.dict
        if enrollment_dict is None:
            continue
        logger.debug(f"Processing enrollment: {enrollment_dict['id']} for section {sections_dict['code']} term {terms[sections_dict['term_code']]['title']}")
        if enrollment_dict.get('status').get('registrationStatus') != "registered":
            logger.debug(f"Skipping enrollment {enrollment_dict['id']} for person {enrollment_dict.get('registrant', {}).get('id')} because registration status is {enrollment_dict.get('status').get('registrationStatus')}")
            continue
        personResourceID = enrollment_dict.get('registrant', {}).get('id')
        if personResourceID and personResourceID not in duplicate_enrollment_ids:
            duplicate_enrollment_ids.add(personResourceID)  # Mark this enrollment as processed
            perf_counter_start = time.perf_counter()
            person = get_person(personResourceID)
            person_times.append(time.perf_counter() - perf_counter_start)
            if person:
                # pprint(person)
                logger.debug(f"Processing enrollment for person ID: {personResourceID} STUDENT)")
                #Fix first name to have None instead of a '.'
                person['names'][0]['firstName']=person['names'][0]['firstName'].strip()[:150] # None create error for first name if it is a '.' so we will fix it here to have None instead of a '.'
                if person['names'][0]['firstName'].strip() == ".":
                    person['names'][0]['firstName'] = None
                user_list.append({
                    "id": get_banner_id(person),
                    "role": "student",
                    "first_name": person['names'][0]['firstName'].strip()[:150],
                    "last_name": person['names'][0]['lastName'].strip()[:150],
                    "email": get_banner_username(person) + "@pipeline.sbcc.edu",
                    "phone_number": None,
                    "address_line1": None, #to be coded later for actual address if needed
                    "address_line_2": None, #to be coded later for actual address if needed
                    "city": None, #to be coded later for actual address if needed
                    "state": None, #to be coded later for actual address if needed
                    "postal_code": None, #to be coded later for actual address if needed
                    "student_major": None, #to be coded later if needed
                    "student_grade_level": "unclassified", #to be coded later if needed
                    "course_number": sections_dict['code'].strip()[:100],
                    "term_code": sections_dict['term_code'].strip()[:20],
                    "term_desc": terms[sections_dict['term_code']]["title"].strip()[:150],
                    "username": get_banner_username(person)
                })
                personCounter += 1
                logger.debug(f"Added person ID: {personResourceID} to user list. Total persons processed: {personCounter}")
# Person processing time statistics
logger.info(f"\nPerson API Call Statistics:")
logger.info(f"Removed outliers using Modified Z-Score method with threshold 3.5")
person_times=remove_outliers_modified_z(person_times, threshold=3.5)
if person_times:
    total_time = sum(person_times)
    average_time = statistics.mean(person_times)
    max_time = max(person_times)
    min_time = min(person_times)
    med = statistics.median(person_times)
    mdev = statistics.median([abs(x - med) for x in person_times])

    
    logger.info(f"Total persons processed: {len(person_times)}")
    logger.info(f"Total time taken: {total_time:.4f} seconds")
    logger.info(f"Average time per person: {average_time:.4f} seconds")
    logger.info(f"Stdev: {statistics.stdev(person_times):.4f}s")
    logger.info(f"Max time for a single person: {max_time:.4f} seconds")
    logger.info(f"Min time for a single person: {min_time:.4f} seconds")
    logger.info(f"Median time for a single person: {med:.4f} seconds")
    logger.info(f"Median absolute deviation: {mdev:.4f} seconds")

logger.info(f"Total number of persons processed: {personCounter}")   

try:
    final_path = create_csv_from_dict_list(user_list, "user")
    user_file_path = final_path
    print(f"Successfully created CSV at: {final_path}")
except ValueError as e:
    logger.error(f"Error: {e}",exc_info=True)

# for  user in user_list:
#     print(user)

# Send the generated CSV files via SFTP to akademos
try:    
    send_file_via_sftp(terms_file_path, f"TEST/term/{terms_file_path.name}")
    send_file_via_sftp(course_file_path, f"TEST/course/{course_file_path.name}")
    send_file_via_sftp(user_file_path, f"TEST/user/{user_file_path.name}")
except Exception as e:
    logger.error(f"Error during SFTP file upload: {e}",exc_info=True)    

# End timer
end_time = time.monotonic()

# Calculate and display runtime
elapsed = end_time - start_time
logger.info(f"Runtime: {format_runtime(elapsed)}")
logger.info("End")