# Akademos SIS Export

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
![Status](https://img.shields.io/badge/Status-Development-yellow)




Python script to extract Banner SIS data to export to Akademos/Vitalsource


## AI Generated Documentation:


***

# 🎓 Akademos SIS Data Export Tool

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-green.svg)]()
[![Status](https://img.shields.io/badge/Status-Complete-brightgreen.svg)]()

This repository contains a robust Python script designed to extract, process, and synchronize academic student information system (SIS) data from an **Ellucian Ethos** instance into structured CSV files, which are then securely uploaded via **SFTP**.

The primary goal of this tool is to generate unified user lists for integration with downstream systems like Akademos.

## ✨ Features

*   **Ellucian Ethos API Integration:** Connects directly to the SIS using API keys and session management (`EllucianEthosPythonClient`).
*   **Comprehensive Data Fetching:** Retrieves academic terms, course sections, registered students, and instructors in a defined workflow.
*   **Performance Optimization:** Utilizes `ThreadPoolExecutor` for concurrent fetching of person records, significantly reducing execution time.
*   **Data Cleaning & Deduplication:** Implements logic to extract Banner IDs (`bannerId`) and usernames (`bannerUserName`), deduplicate entries (based on ID/Role/Course/Term), and clean personal data fields.
*   **Robust Logging:** Includes detailed logging setup to both the console and a rotating file (`logs/akademos_sis_export.log`).
*   **Secure Transfer:** Handles secure file transfer using `paramiko` for uploading compiled CSV files via SFTP.

## 🚀 Getting Started

### Prerequisites

Before running the script, ensure you have:

1.  **Python:** Python 3.8+ is recommended (The current requirement in `pyproject.toml` is `>=3.14`, but stick to a recent stable version for compatibility unless testing explicitly on 3.14).
2.  **Ellucian Ethos API Access:** Valid base URL and Developer API Key.
3.  **SFTP Credentials:** Host, port, username, and password for the target SFTP server.

### Installation

1.  **Clone the Repository:**
    ```bash
    git clone [repository-url]
    cd akademos-sis-export
    ```

2.  **Install Dependencies:**
    The required libraries are defined in `pyproject.toml`. You can install them using a modern Python package manager:

    ```bash
    pip install -r requirements.txt # Or use poetry/pipenv based on your setup
    # Based on pyproject.toml, running this might be sufficient for basic dependencies:
    pip install ellucianethospythonclient paramiko python-dateutil python-dotenv statistics
    ```

### Environment Configuration

The script relies heavily on environment variables configured in a `.env` file. Create a file named **`.env`** in the project root and populate it with your credentials:

***Example Structure (using data from `env.example`):***

```ini
# ====================== AKADEMOS SIS EXPORT ======================

# Ethos API Configuration
ETHOSBASEURL=https://your-ethos-instance.ellucian.cloud
MSGETHOSDEVAPIKEY=your-ethos-api-key-here

# SFTP Configuration (for uploading to Akademos)
SFTPSERVER=your.sftp.server.com
SFTPPORT=22
SFTPUSERNAME=your_sftp_username
SFTPPASSWORD=your_sftp_password

# Logging Configuration
LOG_LEVEL_CONSOLE=INFO    # Options: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL_FILE=DEBUG      # Options: DEBUG, INFO, WARNING, ERROR

# Performance / Concurrency (Adjust these based on network stability and required speed)
PERSON_FETCH_WORKERS=25   # Number of concurrent threads for fetching person details
PERSON_PROGRESS_INTERVAL=100 # Log progress every N persons fetched
COLLECTION_PROGRESS_INTERVAL=50 # Log collection progress every N sections processed

# Optional (Placeholder)
ENVIRONMENT=development
```

## 🛠️ Usage

Execute the main script:

```bash
python akademos_sis_export.py
```

### Execution Flow

The script performs the following sequence of actions:

1.  **Initialization:** Sets up logging and initializes the connection to the Ethos API.
2.  **Term Extraction (Terms):** Fetches all active academic periods (`terms`) and saves them as `data/terms_*.csv`.
3.  **Section Extraction (Course):** Iterates through each term, fetching associated sections. It enriches each section with details from the connected course and subject records. These are saved as `data/course_*.csv`.
4.  **Collection Phase:**
    *   For every processed section, it queries for all **instructors** (`section-instructors`) and **registered students** (`section-registrations`).
    *   All unique Person IDs (PIDs) found are collected into a set.
5.  **Concurrent Fetch (Persons):** Uses multi-threading to concurrently fetch detailed profile data (name, address, credentials like Banner ID) for all unique PIDs from the Ethos API. This is the most time-consuming step and benefits greatly from parallelization.
6.  **Data Aggregation & Deduplication:** Merges the collected personal data with section enrollment records, generating a final list of standardized users (`user_list`). Deduplicates records based on a unique combination of `(Banner ID, Role, Course Code, Term Code)`.
7.  **Final Output (User):** Creates the master user CSV file: `data/user_*.csv`.
8.  **SFTP Upload:** Uploads all generated files (`terms`, `course`, `user`) to the remote SFTP server in a predefined path structure, logging success or failure for each upload.

## 📂 Output Structure

Upon successful execution, the following artifacts are created:

### Local Files (in `./data/` directory)
| Filename Pattern | Description | Content Type |
| :--- | :--- | :--- |
| `terms_[timestamp].csv` | List of all active academic terms. | CSV |
| `course_[timestamp].csv` | Master list of sections, linking courses and departments to specific terms. | CSV |
| `user_[timestamp].csv` | **The primary output.** Consolidated user records for both students (`role: student`) and instructors (`role: professor`), formatted for the target system. | CSV |

### Remote SFTP Uploads
The following files are uploaded to the designated path structure on your remote server:

*   **`/PROD/term/{terms_file_name}`:** The term list file.
*   **`/PROD/course/{course_file_name}`:** The course/section master file.
*   **`/PROD/user/{user_file_name}`:** The final, processed user record file.

## ⚠️ Error Handling & Logging

The script includes extensive error handling for:
*   Missing environment variables (SFTP credentials).
*   API connection failures.
*   Data processing errors (e.g., non-numeric input where numbers are expected).

All activity is logged to the console and, more verbosely, to `logs/akademos_sis_export.log`.

### Advanced Logging Options

You can adjust logging verbosity in your `.env` file:
*   **`LOG_LEVEL_CONSOLE`**: Set to `DEBUG` to see every API request detail, or `INFO` for general execution milestones.
*   **`LOG_LEVEL_FILE`**: Controls the log file's level (defaulting to `DEBUG`).

