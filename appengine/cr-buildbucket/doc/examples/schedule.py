# This example uses Google APIs Client for Python, you can download it here:
# https://developers.google.com/api-client-library/python/

import apiclient
import json

DISCOVERY_URL = (
  'https://cr-buildbucket-test.appspot.com/_ah/api/discovery/v1/apis/'
  '{api}/{apiVersion}/rest')
AUTH_SCOPE = 'email'

# Create buildbucket client using Google APIs Client for Python
buildbucket = apiclient.discovery.build(
  'buildbucket', 'v1',
  discoveryServiceUrl=DISCOVERY_URL,
)

# Schedule a build in "test" bucket with builder_name=my_builder parameter.
# This bucket allows to submit builds to anyone.
req = buildbucket.put(body={
  'bucket': 'test',
  'parameters_json': json.dumps({
    'builder_name': 'my_builder',
  }),
})
print req.execute()
