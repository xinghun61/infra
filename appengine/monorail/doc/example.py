# This example uses Google APIs Client for Python, you can download it here:
# https://developers.google.com/api-client-library/python/

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import apiclient

import httplib2

from oauth2client.file import Storage


DISCOVERY_URL = (
    'https://monorail-staging.appspot.com/_ah/api/discovery/v1/apis/'
    '{api}/{apiVersion}/rest')


# Get credentials to authorize http object
storage = Storage('Your-local-credential-file')
credentials = storage.get()
http = credentials.authorize(httplib2.Http())

# Create monorail client using Google APIs Client for Python
monorail = apiclient.discovery.build(
    'monorail', 'v1',
    discoveryServiceUrl=DISCOVERY_URL,
    http=http)

# Create a chromium project issue
insert_response = monorail.issues().insert(projectId='chromium', body={
    'summary': 'Strange grinding sound',
    'status': 'Untriaged',
    'cc': [{'name':'user1@example.org'}, {'name':'user2@example.org'}]
}).execute()

new_issue_id = insert_response['id']

# Get all issues of chromium
list_response = monorail.issues().list(projectId='chromium').execute()
issues = list_response['items']
total_issues = list_response['totalResults']
