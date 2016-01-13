# This example uses Google APIs Client for Python, you can download it here:
# https://developers.google.com/api-client-library/python/

import apiclient
import httplib2

from oauth2client.file import Storage


DISCOVERY_URL = (
    'https://monorail-staging.appspot.com/_ah/api/discovery/v1/apis/'
    '{api}/{apiVersion}/rest')


# Get credentials to authorize http object
storage = Storage('Your-local-credential-file')
storage.acquire_lock()
credentials = storage.get()
http = credentials.authorize(httplib2.Http())

# Create monorail client using Google APIs Client for Python
monorail = apiclient.discovery.build(
    'monorail', 'v1',
    discoveryServiceUrl=DISCOVERY_URL,
    http=http)

# Get all issues of chromium
issues = monorail.issues().list(projectId='chromium').execute()