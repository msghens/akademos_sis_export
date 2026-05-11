import sys
import os
from pprint import pprint
from dotenv import load_dotenv

# This sample uses a resource iterator to list all the academic periods

import EllucianEthosPythonClient
load_dotenv()

ethosBaseURL = os.environ["ETHOSBASEURL"]
ethosAppAPIKey = os.environ["MSGETHOSDEVAPIKEY"]