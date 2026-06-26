import csv
import datetime
import logging
import logging.handlers
import os
import socket
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import EllucianEthosPythonClient
import paramiko
from dateutil import parser
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv


# ====================== LOGGING SETUP ======================
def setup_logging() -> logging.Logger:
    """Production-ready logging configuration."""
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "akademos_sis_export.log"

    logger = logging.getLogger("akademos_sis")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(os.getenv("LOG_LEVEL_CONSOLE", "INFO").upper())
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating File Handler
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding='utf-8',
        delay=True
    )
    file_handler.setLevel(os.getenv("LOG_LEVEL_FILE", "DEBUG").upper())
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Silence noisy libraries
    for lib in ["paramiko", "urllib3", "requests", "EllucianEthosPythonClient"]:
        logging.getLogger(lib).setLevel(logging.WARNING)

    logger.info("Logging system initialized")
    return logger


# Load environment variables
load_dotenv()

# Initialize logger
logger = setup_logging()

# Start timer
start_time = time.monotonic()
logger.info("=== Starting Akademos SIS Export ===")
logger.info(f"Python version: {sys.version.split()[0]}")

# Global caches
courseCache: Dict[str, dict] = {}
subjectCache: Dict[str, dict] = {}
personCache: Dict[str, dict] = {}

# Ethos API setup
ethosBaseURL = os.environ["ETHOSBASEURL"]
ethosAppAPIKey = os.environ["MSGETHOSDEVAPIKEY"]

# Initialize Ethos API client
ethosClient = EllucianEthosPythonClient.EllucianEthosAPIClient(baseURL=ethosBaseURL)
loginSession = ethosClient.getLoginSessionFromAPIKey(apiKey=ethosAppAPIKey)

logger.info("Ethos API client initialized successfully")


# ====================== HELPER FUNCTIONS ======================
def remove_outliers_modified_z(data, threshold=3.5):
    if not data:
        return []
    try:
        data = [float(x) for x in data]
    except ValueError:
        logger.error("All elements in data list must be numeric", exc_info=True)
        raise

    median_val = statistics.median(data)
    abs_devs = [abs(x - median_val) for x in data]
    mad = statistics.median(abs_devs)

    if mad == 0:
        return data

    modified_z_scores = [0.6745 * (x - median_val) / mad for x in data]
    filtered = [x for x, mz in zip(data, modified_z_scores) if abs(mz) <= threshold]
    return filtered


# SFTP Upload Function
def send_file_via_sftp(local_file_path: Path, remote_file_path: str) -> None:
    """Upload file to SFTP server."""
    if not local_file_path.exists():
        logger.error(f"Local file not found: {local_file_path}")
        raise FileNotFoundError(f"Local file not found: {local_file_path}")

    sftp_server = os.getenv("SFTPSERVER")
    sftp_port = int(os.getenv("SFTPPORT", 22))
    sftp_username = os.getenv("SFTPUSERNAME")
    sftp_password = os.getenv("SFTPPASSWORD")

    if not all([sftp_server, sftp_username, sftp_password]):
        logger.error("Missing SFTP environment variables")
        raise ValueError("Missing SFTP credentials")

    ssh_client = None
    sftp = None
    try:
        logger.info(f"Connecting to SFTP server {sftp_server}")
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(hostname=sftp_server, port=sftp_port, username=sftp_username,
                           password=sftp_password, timeout=15)

        sftp = ssh_client.open_sftp()
        sftp.put(str(local_file_path), remote_file_path)
        logger.info(f"Successfully uploaded {local_file_path.name} to {remote_file_path}")
    except Exception as e:
        logger.error(f"SFTP upload failed for {local_file_path.name}", exc_info=True)
        raise
    finally:
        if sftp:
            sftp.close()
        if ssh_client:
            ssh_client.close()


# Humanize runtime for logging
def format_runtime(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    parts = []
    if hours > 0: parts.append(f"{hours}h")
    if minutes > 0: parts.append(f"{minutes}m")
    if secs > 0: parts.append(f"{secs}s")
    if millis > 0 and hours == 0: parts.append(f"{millis}ms")
    return " ".join(parts) or "0s"


def get_start_date() -> str:
    current = datetime.datetime.now(datetime.timezone.utc)
    six_months_ago = current - relativedelta(months=6)
    return six_months_ago.replace(hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%dT%H:%M:%SZ')


def get_end_date() -> str:
    current = datetime.datetime.now(datetime.timezone.utc)
    two_months_later = current + relativedelta(months=2)
    return two_months_later.replace(hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%dT%H:%M:%SZ')


#===================== CSV CREATION FUNCTION ======================
def create_csv_from_dict_list(data_list: List[Dict[str, Any]], file_prefix: str) -> Path:
    if not data_list:
        raise ValueError("Input data_list cannot be empty.")

    fieldnames = list(data_list[0].keys())
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{file_prefix}_{timestamp}.csv"

    output_dir = Path("data")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file_path = output_dir / filename

    with open(output_file_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data_list)

    return output_file_path


def find_greater(a: Optional[Union[int, float]], b: Optional[Union[int, float]]) -> Optional[Union[int, float]]:
    if a is None and b is None: return None
    if a is None: return b
    if b is None: return a
    return max(a, b)


#
def get_course(course_id: str) -> dict:
    if course_id in courseCache:
        return courseCache[course_id]
    course = ethosClient.getResource(loginSession=loginSession, resourceName="courses", resourceID=course_id)
    result = course.dict if course else {}
    courseCache[course_id] = result
    return result


# Ethos API call to fetch subject details with caching
def get_subject(subject_id: str) -> dict:
    if subject_id in subjectCache:
        return subjectCache[subject_id]
    subject = ethosClient.getResource(loginSession=loginSession, resourceName="subjects", resourceID=subject_id)
    result = subject.dict if subject else {}
    subjectCache[subject_id] = result
    return result


#
def get_person(person_id: str) -> dict:
    if person_id in personCache:
        return personCache[person_id]
    person = ethosClient.getResource(loginSession=loginSession, resourceName="persons", resourceID=person_id)
    result = person.dict if person else {}
    if result:
        personCache[person_id] = result
    return result


#====================== PERSON ATTRIBUTE EXTRACTION ======================
def get_banner_id(person: dict) -> str:
    for credential in person.get('credentials', []):
        if credential.get('type') == 'bannerId':
            return credential.get('value', '').strip()[:50]
    return ""


#
def get_banner_username(person: dict) -> str:
    for credential in person.get('credentials', []):
        if credential.get('type') == 'bannerUserName':
            return credential.get('value', '').strip()[:50]
    return ""


# ====================== MAIN EXECUTION ======================
params = {}
params["criteria"] = '{"category":{"type":"term"},"registration":"open"}'

logger.info("Fetching academic periods")
academicPeriodIterator = ethosClient.getResourceIterator(
    loginSession=loginSession, resourceName="academic-periods", params=params, pageSize=100
)

terms = {}
for period in academicPeriodIterator:
    period_dict = period.dict
    if period_dict:
        terms[period_dict['code']] = {
            "startOn": period_dict['startOn'],
            "endOn": period_dict['endOn'],
            "registration": period_dict['registration'],
            "id": period_dict['id'],
            "title": period_dict['title']
        }

# Terms CSV
term_list = [
    {
        "term_code": code.strip()[:20],
        "start_date": details["startOn"].split('T')[0],
        "end_date": details["endOn"].split('T')[0]
    }
    for code, details in terms.items()
]
term_list.sort(key=lambda x: x["start_date"])

try:
    terms_file_path = create_csv_from_dict_list(term_list, "terms")
    logger.info(f"Created terms CSV: {terms_file_path.name}")
except Exception as e:
    logger.error("Failed to create terms CSV", exc_info=True)

# Sections
sections_raw_list = []
sections_list = []
number_of_sections = 0

logger.info(f"Fetching sections for {len(terms)} terms")

#===================== FETCH SECTIONS ======================
for code, details in terms.items():
    params["criteria"] = f'{{"academicPeriod":{{"id":"{details["id"]}"}},"status":"open"}}'
    sectionsIterator = ethosClient.getResourceIterator(
        loginSession=loginSession, resourceName="sections", params=params, pageSize=500
    )
    for section in sectionsIterator:
        if not section.dict:
            continue
        course_dict = get_course(section.dict['course']['id'])
        if not course_dict or "NC" in course_dict.get('number', ''):
            continue

        sections_raw_list.append(section)
        sections_dict = section.dict
        subject_dict = get_subject(course_dict['subject']['id'])
        course_credit = find_greater(
            course_dict.get('credits', [{}])[0].get('minimum'),
            course_dict.get('credits', [{}])[0].get('maximum')
        )

        sections_list.append({
            "course_number": sections_dict['code'].strip()[:100],
            "course_title": sections_dict['title'].strip()[:100],
            "course_name": subject_dict.get('abbreviation', '').strip()[:60],
            "course_code": course_dict.get('number', '').strip()[:60],
            "course_section": sections_dict['number'].strip()[:60],
            "course_credit": str(course_credit)[:3] if course_credit else "0",
            "course_model": None,
            "department_code": subject_dict.get('abbreviation', '').strip()[:20],
            "department_desc": subject_dict.get('title', '').strip()[:150],
            "campus_code": None,
            "campus_desc": None,
            "term_code": code.strip()[:20],
            "term_desc": terms[code]["title"].strip()[:150],
            "session_code": None,
            "start_date": sections_dict.get("startOn", "").split('T')[0],
            "end_date": sections_dict.get("endOn", "").split('T')[0],
            "enrollment_cap": int(str(sections_dict.get('maxEnrollment', 0))[:4])
        })
        number_of_sections += 1

try:
    course_file_path = create_csv_from_dict_list(sections_list, "course")
    logger.info(f"Created course CSV: {course_file_path.name}")
except Exception as e:
    logger.error("Failed to create course CSV", exc_info=True)

logger.info(f"Total sections processed: {number_of_sections}")

# ====================== CONCURRENT PERSON FETCHING ======================
logger.info("Collecting instructor and student records")

all_person_ids = set()
instructor_data = []
enrollment_data = []

for sections in sections_raw_list:
    sections_dict = sections.dict
    if not sections_dict:
        continue

    term_code = sections_dict.get('term_code')
    course_code = sections_dict.get('code', '').strip()[:100]
    term_desc = terms.get(term_code, {}).get("title", "").strip()[:150]

    params["criteria"] = f'{{"section":{{"id":"{sections_dict.get("guid")}"}}}}'

    # Instructors
    for instructor in ethosClient.getResourceIterator(
            loginSession=loginSession, resourceName="section-instructors", version="10", params=params):
        pid = instructor.dict.get('instructor', {}).get('id')
        if pid:
            all_person_ids.add(pid)
            instructor_data.append({
                'person_id': pid, 'course_code': course_code,
                'term_code': term_code, 'term_desc': term_desc
            })

    # Students
    for enrollment in ethosClient.getResourceIterator(
            loginSession=loginSession, resourceName="section-registrations", version="16", params=params):
        enrollment_dict = enrollment.dict
        if not enrollment_dict or enrollment_dict.get('status', {}).get('registrationStatus') != "registered":
            continue
        pid = enrollment_dict.get('registrant', {}).get('id')
        if pid:
            all_person_ids.add(pid)
            enrollment_data.append({
                'person_id': pid, 'course_code': course_code,
                'term_code': term_code, 'term_desc': term_desc
            })

total_persons = len(all_person_ids)
logger.info(f"Found {total_persons} unique persons")

max_workers = int(os.getenv("PERSON_FETCH_WORKERS", 25))
progress_interval = int(os.getenv("PERSON_PROGRESS_INTERVAL", 100))

#===================== CONCURRENT FETCH FUNCTION ======================
def fetch_person(person_id: str):
    start = time.perf_counter()
    try:
        person = get_person(person_id)
        return person, time.perf_counter() - start
    except Exception as e:
        logger.error(f"Failed to fetch person {person_id}", exc_info=True)
        return {}, time.perf_counter() - start

persons_dict = {}
person_times = []
processed_count = 0

#====================== CONCURRENT FETCH ======================
logger.info(f"Starting concurrent fetch with {max_workers} workers")
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    future_to_pid = {executor.submit(fetch_person, pid): pid for pid in all_person_ids}
    for future in concurrent.futures.as_completed(future_to_pid):
        pid = future_to_pid[future]
        try:
            person, elapsed = future.result()
            persons_dict[pid] = person
            person_times.append(elapsed)
        except Exception:
            persons_dict[pid] = {}
            person_times.append(0.0)

        processed_count += 1
        if processed_count % progress_interval == 0:
            pct = (processed_count / total_persons) * 100
            logger.info(f"Progress: {processed_count}/{total_persons} persons ({pct:.1f}%)")

# Person statistics
if person_times:
    logger.info("=== Person API Call Statistics ===")
    clean_times = remove_outliers_modified_z(person_times, 3.5)
    if clean_times:
        logger.info(f"Total persons: {len(person_times)} | Avg: {statistics.mean(clean_times):.4f}s | Median: {statistics.median(clean_times):.4f}s")

# Build user_list with deduplication
user_list = []
personCounter = 0
duplicate_counter = 0
seen = set()

# Instructors
for data in instructor_data:
    person = persons_dict.get(data['person_id'], {})
    if not person:
        continue
    banner_id = get_banner_id(person)
    if not banner_id:
        continue

    banner_username = get_banner_username(person)
    first_name = person.get('names', [{}])[0].get('firstName', '')
    if isinstance(first_name, str):
        first_name = first_name.strip()[:150]
        if first_name == ".":
            first_name = None

    key = (banner_id, "professor", data['course_code'], data['term_code'])
    if key in seen:
        duplicate_counter += 1
        logger.debug(f"Skipped duplicate instructor {banner_id} in {data['course_code']}")
        continue
    seen.add(key)

    user_list.append({
        "id": banner_id,
        "role": "professor",
        "first_name": first_name,
        "last_name": person.get('names', [{}])[0].get('lastName', '').strip()[:150],
        "email": f"{banner_username}@pipeline.sbcc.edu" if banner_username else None,
        "phone_number": None,
        "address_line1": None,
        "address_line_2": None,
        "city": None,
        "state": None,
        "postal_code": None,
        "student_major": None,
        "student_grade_level": None,
        "course_number": data['course_code'],
        "term_code": data['term_code'],
        "term_desc": data['term_desc'],
        "username": banner_username
    })
    personCounter += 1

# Students
for data in enrollment_data:
    person = persons_dict.get(data['person_id'], {})
    if not person:
        continue
    banner_id = get_banner_id(person)
    if not banner_id:
        continue

    banner_username = get_banner_username(person)
    first_name = person.get('names', [{}])[0].get('firstName', '')
    if isinstance(first_name, str):
        first_name = first_name.strip()[:150]
        if first_name == ".":
            first_name = None

    key = (banner_id, "student", data['course_code'], data['term_code'])
    if key in seen:
        duplicate_counter += 1
        logger.debug(f"Skipped duplicate student {banner_id} in {data['course_code']}")
        continue
    seen.add(key)

    user_list.append({
        "id": banner_id,
        "role": "student",
        "first_name": first_name,
        "last_name": person.get('names', [{}])[0].get('lastName', '').strip()[:150],
        "email": f"{banner_username}@pipeline.sbcc.edu" if banner_username else None,
        "phone_number": None,
        "address_line1": None,
        "address_line_2": None,
        "city": None,
        "state": None,
        "postal_code": None,
        "student_major": None,
        "student_grade_level": "unclassified",
        "course_number": data['course_code'],
        "term_code": data['term_code'],
        "term_desc": data['term_desc'],
        "username": banner_username
    })
    personCounter += 1

logger.info(f"Total persons added after deduplication: {personCounter}")
if duplicate_counter:
    logger.info(f"Skipped {duplicate_counter} duplicate entries")

# Create user CSV
try:
    user_file_path = create_csv_from_dict_list(user_list, "user")
    logger.info(f"Created user CSV: {user_file_path.name}")
except Exception as e:
    logger.error("Failed to create user CSV", exc_info=True)

# SFTP Upload
logger.info("Starting SFTP uploads")
try:
    send_file_via_sftp(terms_file_path, f"TEST/term/{terms_file_path.name}")
    send_file_via_sftp(course_file_path, f"TEST/course/{course_file_path.name}")
    send_file_via_sftp(user_file_path, f"TEST/user/{user_file_path.name}")
    logger.info("All files uploaded successfully")
except Exception as e:
    logger.error("One or more SFTP uploads failed", exc_info=True)

# Final Summary
end_time = time.monotonic()
elapsed = end_time - start_time
logger.info("=== Akademos SIS Export Completed Successfully ===", extra={
    "duration": format_runtime(elapsed),
    "terms": len(terms),
    "sections": number_of_sections,
    "users": len(user_list),
    "duplicates_skipped": duplicate_counter
})
logger.info(f"Total runtime: {format_runtime(elapsed)}")