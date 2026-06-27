# Akademos SIS Export

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
![Status](https://img.shields.io/badge/Status-Development-yellow)




Python script to extract Banner SIS data to export to Akademos/Vitalsource


## AI Generated Documentation:


***

# 🎓 Akademos SIS Data Export Pipeline

A robust Python utility designed to extract core academic data (Terms, Sections, Instructors, Students) from an Ellucian Ethos API endpoint, process it locally, deduplicate records, and securely upload the resulting structured CSV files via SFTP.

This pipeline ensures that all necessary related person details are fetched efficiently using concurrent processing for maximum performance.

## ✨ Features

*   **API Integration:** Connects to Ellucian Ethos API using OAuth/API Key authentication.
*   **Data Enrichment:** Fetches and links data from multiple resources (`academic-periods`, `sections`, `courses`, `subjects`, `section-instructors`, `section-registrations`).
*   **Concurrency:** Utilizes `concurrent.futures` (ThreadPoolExecutor) to fetch detailed person records in parallel, significantly reducing execution time for large datasets.
*   **Data Cleaning & Modeling:** Implements functions like outlier detection (`remove_outliers_modified_z`) and sophisticated deduplication logic based on key identifiers (e.g., `bannerId`, role).
*   **Robust Logging:** Includes a detailed logging setup writing to both standard output and rotating log files, ensuring auditability.
*   **Secure Transfer:** Uploads final structured data files via SFTP using the `paramiko` library.

## 🛠️ Prerequisites & Setup

### Python Requirements

This project requires Python 3.8+ and the following libraries:

```bash
pip install pandas paramiko python-dotenv dateutil ethos-client # (Assuming EllucianEthosPythonClient is packaged or available)
# Note: If 'EllucianEthosPythonClient' is a local package, ensure it is installed/accessible in your PYTHONPATH.
```

### Environment Variables

The script relies heavily on environment variables for secure configuration. You must create a `.env` file (or set these variables directly in your execution environment) containing the following keys:

| Variable | Purpose | Example Value | Required? | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `ETHOSBASEURL` | Base URL for the Ethos API. | `https://ethos-dev.example.edu/api` | Yes | |
| `MSGETHOSDEVAPIKEY` | API Key for authenticating with Ethos. | `your_secret_api_key` | Yes | Used to generate the login session. |
| `SFTPSERVER` | Hostname of the SFTP server. | `sftp.example.edu` | Yes | |
| `SFTPUSERNAME` | Username for SFTP access. | `user_export` | Yes | |
| `SFTPPASSWORD` | Password for SFTP access. | `securepassword123` | Yes | Consider using SSH keys instead of passwords for production. |

### Optional Variables (Tuning)

You can optimize the script's behavior by setting these optional variables:

*   `LOG_LEVEL_CONSOLE`: Sets logging level for console output (`INFO`, `DEBUG`).
*   `LOG_LEVEL_FILE`: Sets logging level for file output (`DEBUG`, `WARNING`).
*   `PERSON_FETCH_WORKERS`: Number of threads to use for concurrent person fetching (Default: 25).
*   `COLLECTION_PROGRESS_INTERVAL`: How often to log progress during section processing.

## 🚀 Usage

### Running the Script

Execute the script from your terminal after setting up the environment variables:

```bash
python path/to/your_script_name.py
```

### Output Files

Upon successful execution, the following structured CSV files will be created in a local `data/` directory and then uploaded to the SFTP server (`TEST/`).

1.  **`terms_[timestamp].csv`**: List of active academic terms.
    *   *Columns:* `term_code`, `start_date`, `end_date`.
2.  **`course_[timestamp].csv`**: Detailed list of all sections available across all terms.
    *   *Columns:* `course_number`, `course_title`, `department_code`, `term_code`, `enrollment_cap`, etc.
3.  **`user_[timestamp].csv`**: The final, deduplicated user roster containing both students and instructors associated with the courses/terms.
    *   *Columns:* Includes detailed fields like `id` (Banner ID), `role` (`student`/`professor`), `first_name`, `last_name`, `email`, etc.

## ⚙️ Technical Workflow Deep Dive

The pipeline follows a multi-stage process:

1.  **Initialization & Connection:**
    *   A detailed logger is initialized for tracking execution flow and errors.
    *   Ethos client connects to the API using environment credentials and retrieves the session token.
2.  **Phase 1: Fetching Academic Context (Terms $\to$ Sections):**
    *   The script first fetches all active academic periods (`academic-periods`).
    *   It then iterates through these terms, fetching all associated sections (`sections`) for each term that is open for registration.
3.  **Phase 2: Collection and Identification:**
    *   For every section found, the pipeline retrieves necessary related metadata (Course details, Subject department).
    *   Crucially, it uses secondary API calls to identify *all* associated person IDs (`pid`) linked to that section via `section-instructors` and `section-registrations`. These PIDs are collected into a master set.
4.  **Phase 3: Concurrent Person Fetching (The Bottleneck):**
    *   Instead of fetching person details sequentially, the script distributes all unique PIDs across a thread pool (`ThreadPoolExecutor`). This maximizes API throughput and minimizes wait time.
5.  **Phase 4: Data Modeling and Deduplication:**
    *   The raw instructor and enrollment records are processed into two lists (Instructors and Students).
    *   A final deduplication pass runs, ensuring that the `user_list` only contains one entry per unique person/role combination for a specific course/term key, preventing redundant data.
6.  **Phase 5: Export & Distribution:**
    *   The structured lists are converted into CSV format using Python's built-in `csv` module.
    *   Finally, the generated files are uploaded to the remote SFTP server for downstream consumption.

## 📚 Discussion Points

### Algorithmic Efficiency (Time Complexity)

The most critical part of this script is **Phase 3: Concurrent Person Fetching**. If $N$ is the total number of unique persons and $T$ is the time taken for a single API call to `get_person`, running sequentially would take $O(N \cdot T)$. By using $W$ workers (where $W$ is `max_workers`), the theoretical complexity approaches $O(\frac{N}{W} \cdot T)$, resulting in massive performance gains.

### Scalability Concerns

1.  **API Rate Limiting:** Given the intensive nature of API calls, high-volume runs must be monitored for rate limits imposed by the Ethos API provider.
2.  **Memory Usage:** If the dataset (number of sections/persons) is extremely large (hundreds of thousands), collecting all `sections_list`, `instructor_data`, and `enrollment_data` into memory before processing could lead to memory exhaustion. For enterprise-scale data, consider implementing a database persistence layer instead of in-memory lists.

---
