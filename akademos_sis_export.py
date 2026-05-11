import sys
import os
from pprint import pprint

# This sample uses a resource iterator to list all the academic periods

import EllucianEthosPythonClient

ethosBaseURL = os.environ["ETHOSBASEURL"]
ethosAppAPIKey = os.environ["ICETHOSDEVAPIKEY"]