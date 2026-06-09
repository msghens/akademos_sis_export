# Akademos SIS Export

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
![Status](https://img.shields.io/badge/Status-Development-yellow)




Python script to extract Banner SIS data to export to Akademos/Vitalsource


## AI Generated Documentation:


As an Advanced Python Code Production Assistant, I recognize this codebase as a sophisticated Extract, Transform, Load (ETL) pipeline. It handles complex interactions with external Student Information Systems (SIS), specifically Ethos, and performs data sanitation, transformation, and file transfer tasks.

I will structure the documentation using clear headings, making it easy for a developer new to the project's logic flow but comfortable with Python development practices.

***

# 📖 Codebase Documentation: Akademos SIS Export Pipeline

## 🎯 Overview: What This Module Does and Why It Exists

This module is an **Academic Data Synchronization Pipeline**. Its primary function is to connect to the Ellucian Ethos Student Information System (SIS) via a REST API, extract critical academic data—including active terms, course sections, course details, instructor profiles, and student enrollment records.

The extracted raw data is then transformed into structured formats (CSV files for Terms, Courses, and Users) and finally transmitted to an external system (Akademos) via Secure File Transfer Protocol (SFTP).

**In essence:** It acts as a nightly job that pulls the definitive academic roster and catalog information from Ethos, ensuring downstream systems like Akademos have up-to-date data for scheduling and user management.

### Key Components:
1.  **Extraction:** Uses `EllucianEthosPythonClient` to query resources (`academic-periods`, `sections`, `courses`, etc.).
2.  **Transformation:** Cleans, normalizes, calculates (e.g., course credit), and aggregates data into defined dictionaries/lists.
3.  **Loading:** Writes structured Python lists to CSV files using `pathlib` and uploads those files via SFTP using `paramiko`.

---

## 🚀 Quick Start: How to Use It

Since this is a large, procedural script designed for scheduled execution (e.g., cron job), the "quick start" focuses on setup rather than calling a single function.

### Prerequisites
1.  **Python Environment:** Python 3.8+
2.  **Dependencies:** Ensure all required libraries are installed:
    ```bash
    pip install paramiko python-dotenv dateutil pyyaml
    # You must also have the Ethos API Client library installed/accessible
    # pip install EllucianEthosPythonClient 
    ```
3.  **Environment Variables:** The script relies heavily on `.env` or system environment variables for connectivity:
    *   `ETHOSBASEURL`: Base URL for the Ethos API.
    *   `MSGETHOSDEVAPIKEY`: API Key for authentication.
    *   `SFTPSERVER`, `SFTPUSERNAME`, `SFTPPASSWORD`, `SFTPPORT`: Credentials for the destination SFTP server.

### Execution (3 Steps)
1. **Set up Environment:** Place your `.env` file in the project root, ensuring all required keys are present.
2. **Run Pipeline:** Execute the script:
    ```bash
    python your_script_name.py
    ```
3. **Check Output:** Verify that the necessary CSV files (`terms_*.csv`, `course_*.csv`, `user_*.csv`) have been generated in the local `data/` directory and successfully uploaded to the specified SFTP path.

---

## 📚 API Reference: Public Functions

This section details all utility functions available for use within the codebase.

### 1. `send_file_via_sftp(local_file_path: Path, remote_file_path: str) -> None`
*   **Purpose:** Handles secure file transfer of a locally generated CSV to the designated SFTP server.
*   **Parameters:**
    *   `local_file_path` (`Path`): The local path object pointing to the file that needs uploading.
    *   `remote_file_path` (`str`): The full destination path on the SFTP server (e.g., `"TEST/course/mydata.csv"`).
*   **Returns:** `None`. Prints success or failure message.
*   **Raises:** `ValueError` if SFTP credentials are missing; general `Exception` upon connection or upload failure.

### 2. `format_runtime(seconds: float) -> str`
*   **Purpose:** Converts a total runtime duration given in seconds into a human-readable, compact string format (e.g., "1h 30m 5s").
*   **Parameters:**
    *   `seconds` (`float`): The duration to format. Must be non-negative.
*   **Returns:** `str`: The formatted runtime string.

### 3. `get_start_date() -> str`
*   **Purpose:** Calculates a date exactly six calendar months prior to the current moment (UTC). Used for defining the start of an academic window.
*   **Parameters:** None.
*   **Returns:** `str`: The calculated date in ISO 8601 format (`YYYY-MM-DDTHH:MM:SSZ`).

### 4. `get_end_date() -> str`
*   **Purpose:** Calculates a date exactly two calendar months after the current moment (UTC). Used for defining the end of an academic window.
*   **Parameters:** None.
*   **Returns:** `str`: The calculated date in ISO 8601 format (`YYYY-MM-DDTHH:MM:SSZ`).

### 5. `create_csv_from_dict_list(data_list: List[Dict[str, Any]], file_prefix: str) -> Path`
*   **Purpose:** The core persistence function. Writes a standardized list of dictionaries into a new CSV file within the local `./data/` directory, using a timestamped filename structure (`{file_prefix}_{timestamp}.csv`).
*   **Parameters:**
    *   `data_list` (`List[Dict[str, Any]]`): The collection of records to be written. **Must not be empty.**
    *   `file_prefix` (`str`): A descriptive prefix for the file (e.g., `"terms"`, `"course"`).
*   **Returns:** `Path`: A `pathlib.Path` object pointing to the successfully created CSV file.
*   **Raises:** `ValueError` if `data_list` is empty.

### 6. `find_greater(a: Optional[Union[int, float]], b: Optional[Union[int, float]]) -> Optional[Union[int, float]]`
*   **Purpose:** Safely compares two optional numerical inputs (`a` and `b`) and returns the greater value while gracefully handling cases where one or both inputs are `None`.
*   **Parameters:**
    *   `a`: The first number (or `None`).
    *   `b`: The second number (or `None`).
*   **Returns:** `Optional[Union[int, float]]`: The maximum valid number found.

### 7. `check_date_range(begin_date_str: str, end_date_str: str) -> bool`
*   **Purpose:** Validates if a given date range falls within an acceptable business window (9 months in the past to 9 months in the future relative to execution time).
*   **Parameters:**
    *   `begin_date_str` (`str`): Start date (ISO format).
    *   `end_date_str` (`str`): End date (ISO format).
*   **Returns:** `bool`: `True` if the range is valid, `False` otherwise.

### 8. `get_course(course_id: str) -> dict`
*   **Purpose:** Retrieves course details from Ethos API. Uses an internal cache (`courseCache`) to prevent redundant API calls for the same course ID.
*   **Parameters:**
    *   `course_id` (`str`): The unique ID of the course resource.
*   **Returns:** `dict`: Dictionary containing course details, or `{}` if not found.

### 9. `get_subject(subject_id: str) -> dict`
*   **Purpose:** Retrieves subject/department details from Ethos API. Uses an internal cache (`subjectCache`).
*   **Parameters:**
    *   `subject_id` (`str`): The unique ID of the subject resource.
*   **Returns:** `dict`: Dictionary containing subject details, or `{}` if not found.

### 10. `get_person(person_id: str) -> dict`
*   **Purpose:** Retrieves detailed person/user profile from Ethos API. Uses an internal cache (`personCache`). This is crucial for fetching names and credentials.
*   **Parameters:**
    *   `person_id` (`str`): The unique ID of the person resource.
*   **Returns:** `dict`: Dictionary containing person details, or `{}` if not found.

### 11. `get_banner_id(person: dict) -> str | None`
*   **Purpose:** Parses a complex person dictionary to extract the Banner unique ID from credentials.
*   **Parameters:**
    *   `person` (`dict`): The result of calling `get_person()`.
*   **Returns:** `str | None`: The extracted Banner ID, or `None`.

### 12. `get_banner_username(person: dict) -> str | None`
*   **Purpose:** Parses a complex person dictionary to extract the user's primary network username (Banner Username).
*   **Parameters:**
    *   `person` (`dict`): The result of calling `get_person()`.
*   **Returns:** `str | None`: The extracted username, or `None`.

---

## 💡 Common Patterns / Use Cases

### Pattern 1: Exporting Core Academic Terms (Read-Only Metadata)
This pattern demonstrates how the system establishes its primary scope by pulling all relevant academic periods first.

```python
# Example: Getting and caching all open terms
params = {}
# The criteria ensures we only look at 'term' category types with open registration
params["criteria"] = '{"category":{"type":"term"},"registration":"open"}' 

academicPeriodIterator = ethosClient.getResourceIterator(
  loginSession=loginSession,
  resourceName="academic-periods",
  version=None,
  params=params,
  pageSize=100
)

terms = {}
for period in academicPeriodIterator:
    period_dict = period.dict
    # Store essential metadata for later use (e.g., term code and dates)
    if period_dict:
        terms[period_dict['code']] = {
            "startOn": period_dict['startOn'], 
            "endOn": period_dict['endOn'], 
            # ... other fields
        }

# Data transformation and export
term_list = []  
for code, details in terms.items():
    term_list.append({
        "term_code": code.strip()[:20],
        "start_date": details["startOn"].split('T')[0],
        "end_date": details["endOn"].split('T')[0]
    })

final_path = create_csv_from_dict_list(term_list, "terms")
```

### Pattern 2: Exporting Course Sections and Catalog Data (The Main Loop)
This pattern is the most resource-intensive. It iterates through terms/sections to build the comprehensive course catalog list. Note how it combines data from three separate API calls (`sections`, `courses`, `subjects`) into one structured record.

```python
# Pseudocode for processing sections:
for code, details in terms.items(): # Iterate over each term found earlier
    params["criteria"] = "{\"academicPeriod\":{\"id\":\"" + details["id"] + "\"},\"status\":\"open\"}"
    sectionsIterator = ethosClient.getResourceIterator(resourceName="sections", ...)

    for section in sectionsIterator:
        # 1. Fetch Course Details (uses cache)
        course_dict = get_course(section.dict['course']['id'])
        if not course_dict: continue

        # 2. Fetch Subject/Department Details (uses cache)
        subject_dict = get_subject(course_dict['subject']['id'])
        if not subject_dict: continue
        
        # 3. Transformation & Calculation
        course_credit = find_greater(course_dict['credits'][0]['minimum'], course_dict['credits'][0]['maximum'])

        sections_list.append({
            "course_number": course_dict['number'].strip(),
            "course_title": course_dict['title'].strip(),
            # ... many other fields populated from the 3 sources
            "department_code": subject_dict['abbreviation'].strip()[:20],
            "course_credit": str(course_credit)[:3] if course_credit else "0",
            # ...
        })
```

### Pattern 3: Exporting User Records (Student and Professor Roster)
This pattern handles the most complex data relationships, involving iteration over sections to find related users. It requires multiple lookups (`section-instructors` and `section-registrations`) followed by person profile retrieval (`get_person`).

```python
# Pseudocode for processing user records:
user_list = []
for sections in sections_raw_list: # Iterate over every valid section found earlier
    sections_dict = sections.dict

    # A. Process Instructors (Professors)
    params["criteria"] = "{\"section\": {\"id\": \"" + sections_dict['guid'] + "\"}}"
    instructorIterator = ethosClient.getResourceIterator(resourceName="section-instructors", ...)
    for instructor in instructorIterator:
        personResourceID = instructor.dict.get('instructor', {}).get('id') 
        if personResourceID:
            # Fetch full profile (uses cache)
            person = get_person(personResourceID) 
            user_list.append({
                "role": "professor",
                "first_name": person['names'][0]['firstName'].strip(),
                # ... other fields
            })

    # B. Process Enrollments (Students)
    params["criteria"] = "{\"section\": {\"id\": \"" + sections_dict['guid'] + "\"}}"
    enrollmentIterator = ethosClient.getResourceIterator(resourceName="section-registrations", ...)
    for enrollment in enrollmentIterator:
        # Check Business Logic: Must be 'registered' status
        if enrollment_dict.get('status').get('registrationStatus') != "registered": continue
        
        personResourceID = enrollment_dict.get('registrant', {}).get('id')
        if personResourceID:
            person = get_person(personResourceID)
            user_list.append({
                "role": "student",
                "first_name": person['names'][0]['firstName'].strip(),
                # ... other fields
            })

final_path = create_csv_from_dict_list(user_list, "user")
```

---

## ⚠️ Gotchas: Edge Cases and Limitations

1.  **Timezone Management (Crucial):** The code makes significant assumptions about timezones. It uses `datetime.timezone.utc` for date calculations (`get_start_date`, `get_end_date`). If the Ethos API or your local environment operates on a different timezone, data comparisons and filtering **will fail silently**.
2.  **API Rate Limiting:** The script makes numerous sequential calls (e.g., one call for every section to get its instructors, another call per section for enrollments). High volume execution could trigger Ethos rate limits or API throttling, causing the process to fail mid-run. *Recommendation: Implement exponential backoff and retry logic.*
3.  **Hardcoded Business Logic:** Several filters are hardcoded (e.g., `if "NC" in course_dict['number']:` to filter out non-credit courses; filtering by `"registration":"open"`). If the business rules change, these lines must be updated manually.
4.  **Error Handling:** The current error handling is basic (`try...except Exception as e: print(f"Error...")`). For production use, you should replace generic `print()` statements with a robust logging framework (e.g., Python's built-in `logging` module) to track failures and context.
5.  **Data Structure Assumptions:** The code relies heavily on the *exact* structure of Ethos API responses (e.g., `person['names'][0]['firstName']`). If the underlying schema changes, any line accessing these nested keys will raise a `KeyError` or `IndexError`.

---

## 🔗 Related Modules and Next Steps

This pipeline is designed to be self-contained but interacts with several concepts that might reside in other modules:

*   **Data Model:** The output CSV schemas define the canonical data model for Akademos. Any change here requires coordination with the downstream system owner.
*   **Authentication:** If this module were part of a larger suite, authentication handling (API key management and session refreshing) should be abstracted into a dedicated `AuthManager` class.
*   **Logging Module:** A separate utility module should handle all logging, centralizing formatters, log levels, and output destinations (file/ELK stack).

***

> **✨ Next Step Recommendation:** I strongly recommend that you ask me to test this code's structure using mock data and monkey patching. This will allow us to simulate the Ethos API calls (`ethosClient.getResource`) without needing actual credentials or risking rate limits, ensuring the entire ETL logic flow is robust before deployment!

