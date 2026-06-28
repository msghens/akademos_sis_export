import csv
import datetime
import logging
import logging.handlers
import os
import socket
import statistics
import sys
import time
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import EllucianEthosPythonClient
import paramiko
from dateutil import parser
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv


# ====================== LOGGING SETUP ======================
def setup_logging() -> logging.Logger:
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

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(os.getenv("LOG_LEVEL_CONSOLE", "INFO").upper())
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

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

    for lib in ["paramiko", "urllib3", "requests", "EllucianEthosPythonClient"]:
        logging.getLogger(lib).setLevel(logging.WARNING)

    logger.info("Logging system initialized")
    return logger


load_dotenv()
logger = setup_logging()

start_time = time.monotonic()
logger.info("=== Starting Akademos SIS Export ===")
logger.info(f"Python version: {sys.version.split()[0]}")

# Caches
courseCache: Dict[str, dict] = {}
subjectCache: Dict[str, dict] = {}
personCache: Dict[str, dict] = {}
SectionRecord = namedtuple('SectionRecord', ['section_obj', 'term_code', 'term_desc'])

ethosBaseURL = os.environ["ETHOSBASEURL"]
ethosAppAPIKey = os.environ["MSGETHOSDEVAPIKEY"]

ethosClient = EllucianEthosPythonClient.EllucianEthosAPIClient(baseURL=ethosBaseURL)
loginSession = ethosClient.getLoginSessionFromAPIKey(apiKey=ethosAppAPIKey)

logger.info("Ethos API client initialized successfully")


# ====================== HELPERS ======================
def remove_outliers_modified_z(data: List, threshold: float = 3.5) -> List[float]:
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
    return [x for x, mz in zip(data, modified_z_scores) if abs(mz) <= threshold]


def send_file_via_sftp(local_file_path: Path, remote_file_path: str) -> None:
    if not local_file_path.exists():
        logger.error(f"Local file not found: {local_file_path}")
        raise FileNotFoundError(f"Local file not found: {local_file_path}")

    sftp_server: Optional[str] = os.getenv("SFTPSERVER")
    sftp_port = int(os.getenv("SFTPPORT", 22))
    sftp_username: Optional[str] = os.getenv("SFTPUSERNAME")
    sftp_password: Optional[str] = os.getenv("SFTPPASSWORD")

    if not sftp_server or not sftp_username or not sftp_password:
        logger.error("Missing required SFTP environment variables (SFTPSERVER, SFTPUSERNAME, SFTPPASSWORD)")
        raise ValueError("Missing SFTP credentials")

    ssh_client = None
    sftp = None
    try:
        logger.info(f"Connecting to SFTP server {sftp_server}:{sftp_port}")
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        ssh_client.connect(
            hostname=sftp_server,           # Now guaranteed to be str (thanks to the check above)
            port=sftp_port,
            username=sftp_username,
            password=sftp_password,
            timeout=15,
            allow_agent=False,
            look_for_keys=False
        )
        
        sftp = ssh_client.open_sftp()
        sftp.put(str(local_file_path), remote_file_path)
        logger.info(f"Successfully uploaded {local_file_path.name} to {remote_file_path}")
        
    except paramiko.AuthenticationException:
        logger.error("SFTP Authentication failed - check credentials", exc_info=True)
        raise
    except paramiko.SSHException as e:
        logger.error(f"SSH error: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"SFTP upload failed", exc_info=True)
        raise
    finally:
        if sftp:
            sftp.close()
        if ssh_client:
            ssh_client.close()


def format_runtime(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    parts = []
    if hours: parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    if secs: parts.append(f"{secs}s")
    if millis and not hours: parts.append(f"{millis}ms")
    return " ".join(parts) or "0s"


def get_start_date() -> str:
    current = datetime.datetime.now(datetime.timezone.utc)
    six_months_ago = current - relativedelta(months=6)
    return six_months_ago.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'


def get_end_date() -> str:
    current = datetime.datetime.now(datetime.timezone.utc)
    two_months_later = current + relativedelta(months=2)
    return two_months_later.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'


def create_csv_from_dict_list(data_list: List[Dict[str, Any]], file_prefix: str) -> Path:
    if not data_list:
        logger.warning(f"No data for {file_prefix} CSV")
        # Return empty file or raise — your choice
        raise ValueError(f"Input data_list for {file_prefix} cannot be empty.")

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

    logger.info(f"Created {file_prefix} CSV with {len(data_list):,} rows: {output_file_path.name}")
    return output_file_path


def find_greater(a: Optional[Union[int, float]], b: Optional[Union[int, float]]) -> Optional[Union[int, float]]:
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    return max(a, b)


def get_course(course_id: str) -> dict:
    if course_id in courseCache:
        return courseCache[course_id]
    course = ethosClient.getResource(loginSession=loginSession, resourceName="courses", resourceID=course_id)
    result: dict = course.dict if course and hasattr(course, 'dict') and course.dict else {}
    courseCache[course_id] = result
    return result


def get_subject(subject_id: str) -> dict:
    if subject_id in subjectCache:
        return subjectCache[subject_id]
    subject = ethosClient.getResource(loginSession=loginSession, resourceName="subjects", resourceID=subject_id)
    result: dict = subject.dict if subject and hasattr(subject, 'dict') and subject.dict else {}
    subjectCache[subject_id] = result
    return result


def get_person(person_id: str) -> dict:
    if person_id in personCache:
        return personCache[person_id]
    person = ethosClient.getResource(loginSession=loginSession, resourceName="persons", resourceID=person_id)
    result: dict = person.dict if person and hasattr(person, 'dict') and person.dict else {}
    if result:
        personCache[person_id] = result
    return result


def get_banner_id(person: dict) -> str:
    for credential in person.get('credentials', []):
        if credential.get('type') == 'bannerId':
            return credential.get('value', '').strip()[:50]
    return ""


def get_banner_username(person: dict) -> str:
    for credential in person.get('credentials', []):
        if credential.get('type') == 'bannerUserName':
            return credential.get('value', '').strip()[:50]
    return ""


# ====================== MAIN EXECUTION ======================
params: Dict[str, str] = {"criteria": '{"category":{"type":"term"},"registration":"open"}'}

logger.info("Fetching academic periods")
academicPeriodIterator = ethosClient.getResourceIterator(
    loginSession=loginSession, resourceName="academic-periods", params=params, pageSize=100
)

terms: Dict[str, Dict[str, Any]] = {}
for period in academicPeriodIterator:
    period_dict = period.dict if hasattr(period, 'dict') else {}
    if period_dict and period_dict.get('code'):
        terms[period_dict['code']] = {
            "startOn": period_dict.get('startOn'),
            "endOn": period_dict.get('endOn'),
            "registration": period_dict.get('registration'),
            "id": period_dict.get('id'),
            "title": period_dict.get('title')
        }

term_list: List[Dict[str, str]] = [
    {
        "term_code": code.strip()[:20],
        "start_date": details["startOn"].split('T')[0] if details.get("startOn") else "",
        "end_date": details["endOn"].split('T')[0] if details.get("endOn") else ""
    }
    for code, details in terms.items()
]
term_list.sort(key=lambda x: x["start_date"])

terms_file_path = create_csv_from_dict_list(term_list, "terms")

# ====================== SECTIONS ======================
sections_raw_list: List[SectionRecord] = []   # Changed to typed records
sections_list: List[Dict[str, Any]] = []
number_of_sections = 0

logger.info(f"Fetching sections for {len(terms)} terms")

for code, details in terms.items():
    params["criteria"] = f'{{"academicPeriod":{{"id":"{details["id"]}"}},"status":"open"}}'
    
    sectionsIterator = ethosClient.getResourceIterator(
        loginSession=loginSession, resourceName="sections", params=params, pageSize=500
    )
    
    for section in sectionsIterator:
        section_dict = section.dict if hasattr(section, 'dict') and section.dict else {}
        if not section_dict:
            continue

        course_dict = get_course(section_dict.get('course', {}).get('id'))
        if not course_dict or "NC" in course_dict.get('number', ''):
            continue

        subject_dict = get_subject(course_dict.get('subject', {}).get('id'))

        course_credit = find_greater(
            course_dict.get('credits', [{}])[0].get('minimum'),
            course_dict.get('credits', [{}])[0].get('maximum')
        )

        sections_list.append({
            "course_number": section_dict.get('code', '').strip()[:100],
            "course_title": section_dict.get('title', '').strip()[:100],
            "course_name": subject_dict.get('abbreviation', '').strip()[:60],
            "course_code": course_dict.get('number', '').strip()[:60],
            "course_section": f"{section_dict.get('code', '').strip()}.{code}".strip()[:60],
            "course_credit": str(course_credit)[:3] if course_credit is not None else "0",
            "course_model": None,
            "department_code": subject_dict.get('abbreviation', '').strip()[:20],
            "department_desc": subject_dict.get('title', '').strip()[:150],
            "campus_code": None,
            "campus_desc": None,
            "term_code": code.strip()[:20],
            "term_desc": details.get("title", "").strip()[:150],
            "session_code": None,
            "start_date": section_dict.get("startOn", "").split('T')[0] if section_dict.get("startOn") else "",
            "end_date": section_dict.get("endOn", "").split('T')[0] if section_dict.get("endOn") else "",
            "enrollment_cap": int(str(section_dict.get('maxEnrollment', 0))[:4])
        })

        # Store with term context for collection phase
        sections_raw_list.append(SectionRecord(
            section_obj=section,
            term_code=code.strip(),
            term_desc=details.get("title", "").strip()[:150]
        ))
        
        number_of_sections += 1

course_file_path = create_csv_from_dict_list(sections_list, "course")
logger.info(f"Total sections processed: {number_of_sections:,}")

# ====================== COLLECTION PHASE ======================
logger.info("Collecting instructor and student records")

all_person_ids: set[str] = set()
instructor_data: List[Dict[str, Any]] = []
enrollment_data: List[Dict[str, Any]] = []

collection_interval = int(os.getenv("COLLECTION_PROGRESS_INTERVAL", 50))
section_count = 0

for record in sections_raw_list:          # Now using our enriched records
    section_dict = record.section_obj.dict if hasattr(record.section_obj, 'dict') else {}
    if not section_dict:
        continue

    course_code = section_dict.get('code', '').strip()[:100]
    term_code = record.term_code
    term_desc = record.term_desc

    # Use 'id' (preferred) or fallback to 'guid'
    section_id = section_dict.get('id') or section_dict.get('guid')
    if not section_id:
        logger.warning(f"Section missing id/guid: {course_code}")
        continue

    params["criteria"] = f'{{"section":{{"id":"{section_id}"}}}}'

    # Instructors
    for instructor in ethosClient.getResourceIterator(
            loginSession=loginSession, 
            resourceName="section-instructors", 
            version="10", 
            params=params):
        instr_dict = instructor.dict if hasattr(instructor, 'dict') else {}
        if not instr_dict:
            continue
        pid = instr_dict.get('instructor', {}).get('id')
        if pid:
            all_person_ids.add(pid)
            instructor_data.append({
                'person_id': pid,
                'course_code': course_code,
                'term_code': term_code,
                'term_desc': term_desc
            })

    # Students
    for enrollment in ethosClient.getResourceIterator(
            loginSession=loginSession, 
            resourceName="section-registrations", 
            version="16", 
            params=params):
        enr_dict = enrollment.dict if hasattr(enrollment, 'dict') else {}
        if not enr_dict:
            continue
        if enr_dict.get('status', {}).get('registrationStatus') != "registered":
            continue
        pid = enr_dict.get('registrant', {}).get('id')
        if pid:
            all_person_ids.add(pid)
            enrollment_data.append({
                'person_id': pid,
                'course_code': course_code,
                'term_code': term_code,
                'term_desc': term_desc
            })

    section_count += 1
    if section_count % collection_interval == 0:
        logger.info(f"Collection progress: {section_count:,}/{len(sections_raw_list):,} sections | "
                    f"{len(all_person_ids):,} unique persons found")

total_persons = len(all_person_ids)
logger.info(f"Collection completed - Found {total_persons:,} unique persons")

# ====================== CONCURRENT FETCH ======================
max_workers = int(os.getenv("PERSON_FETCH_WORKERS", 25))
progress_interval = int(os.getenv("PERSON_PROGRESS_INTERVAL", 100))

def fetch_person(person_id: str):
    start = time.perf_counter()
    try:
        person = get_person(person_id)
        return person, time.perf_counter() - start
    except Exception as e:
        logger.error(f"Failed to fetch person {person_id}", exc_info=True)
        return {}, time.perf_counter() - start

persons_dict: Dict[str, dict] = {}
person_times: List[float] = []
processed_count = 0

logger.info(f"Starting concurrent fetch with {max_workers} workers")
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    future_to_pid = {executor.submit(fetch_person, pid): pid for pid in all_person_ids}
    for future in as_completed(future_to_pid):
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
            pct = (processed_count / total_persons) * 100 if total_persons > 0 else 0
            logger.info(f"Fetch progress: {processed_count}/{total_persons} persons ({pct:.1f}%)")

# Person statistics
if person_times:
    logger.info("=== Person API Call Statistics ===")
    # Remove outliers using modified Z-score method
    # clean_times = remove_outliers_modified_z(person_times)
    clean_times = person_times  # For now, we keep all times; uncomment above line to remove outliers
    if clean_times:
        logger.info(f"Processed {len(clean_times)} persons | Avg: {statistics.mean(clean_times):.4f}s")
        logger.info(f"Min: {min(clean_times):.4f}s | Max: {max(clean_times):.4f}s | Median: {statistics.median(clean_times):.4f}s")
        logger.info(f"Std Dev: {statistics.stdev(clean_times):.4f}s | 25th Percentile: {statistics.quantiles(clean_times, n=4)[0]:.4f}s | 75th Percentile: {statistics.quantiles(clean_times, n=4)[2]:.4f}s")
        logger.info(f"Total API time: {sum(clean_times):.4f}s | Total calls: {len(clean_times)}")
        logger.info(f"Total elapsed time: {time.perf_counter() - start_time:.4f}s")

# Build user_list with deduplication
user_list: List[Dict[str, Any]] = []
personCounter = 0
duplicate_counter = 0
seen: set[tuple] = set()

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
        logger.debug(f"Skipped duplicate instructor {banner_id}")
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
        logger.debug(f"Skipped duplicate student {banner_id}")
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
    user_file_path = None

# SFTP Upload
logger.info("Starting SFTP uploads")
try:
    if terms_file_path:
        send_file_via_sftp(terms_file_path, f"TEST/term/{terms_file_path.name}")
    if course_file_path:
        send_file_via_sftp(course_file_path, f"TEST/course/{course_file_path.name}")
    if user_file_path:
        send_file_via_sftp(user_file_path, f"TEST/user/{user_file_path.name}")
    logger.info("All files uploaded successfully")
except Exception as e:
    logger.error("SFTP upload failed", exc_info=True)

# Final summary
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