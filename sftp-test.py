

# Test SFTP connection and file upload to bettern understand how to send the generated CSV files to akademos via SFTP. This is a standalone script that can be run independently of the main export script.
import os

import paramiko
from dotenv import load_dotenv

load_dotenv()
SFTP_SERVER = os.getenv("SFTPSERVER")
SFTP_USERNAME = os.getenv("SFTPUSERNAME")
SFTP_PASSWORD = os.getenv("SFTPPASSWORD")
SFTP_PORT = int(os.getenv("SFTPPORT"))





client = paramiko.Transport((SFTP_SERVER, SFTP_PORT))
client.connect(username=SFTP_USERNAME, password=SFTP_PASSWORD)

sftp = paramiko.SFTPClient.from_transport(client)
for filename in sftp.listdir():
    print(filename) 
sftp.close()
client.close()