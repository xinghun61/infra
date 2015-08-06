# Buildbot master authentication to Cloud Endpoints

*** promo
TL;DR Each master may have a service account assigned to it. Two modules
[auth.py](https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/master/auth.py)
and
[deferred_resource.py](https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/master/deferred_resource.py)
together can be used to make authenticated Cloud Endpoints API calls.
***

[TOC]

## Master service accounts

Each master may have a service account assigned:

```python
# master_site_config.py
class MyMaster(Master3):
  # other stuff
  service_account_file = 'service-account-myproject.json'
```

Service account files should always be named
"service-account-[shortname].json". If `service_account_file` attribute
is set, `service_account_path` attribute is resolved to
`[CREDENTIALS_DIR]/[service_account_file]`. In order to request a
service account for your master,
[file a bug](https://code.google.com/p/chromium/issues/entry?template=Build%20Infrastructure&labels=Infra-Labs,Restrict-View-Google&summary=Service%20account%20[short%20name]%20for%20master.[master_name]&comment=Please%20provide%20a%20service%20account%20json%20key%20file%20%22service-account-[short%20name].json%22%20on%20[master%20machine].%0A%0DInstructions%20for%20admins%20to%20create%20service%20accounts:%20https://sites.google.com/a/google.com/chrome-infrastructure/appspot-instances/buildbot-master-authentication-to-gae-apps).

One service account can be used to authorize calls to different GAE
apps.

## Making authenticated API calls

TL;DR Use
[deferred_resource.py](https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/master/deferred_resource.py)
to generate an API client for Twisted code at runtime. Use
[auth.py](https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/master/auth.py)
to sign it.

```python
from master import auth
from master import deferred_resource

MY_SERVICE_HOSTNAME = 'my_service.appspot.com'
MY_SERVICE_DISCOVERY_URL = (
  '%s/_ah/api/discovery/v1/apis/{api}/{apiVersion}/rest' %
  MY_SERVICE_HOSTNAME
)

@defer.inlineCallbacks
def greet(active_master):
  # active_master is master configuration,
  # what is normally called ActiveMaster in master.cfg

  # Create a signed httplib.Http2 factory.
  http_factory = lambda: auth.create_http(active_master)

  # Create API client for Twisted.
  my_service = yield deferred_resource.DeferredResource.build(
      'my_service',
      'v1',
      http_factory=http_factory,
      discoveryServiceUrl=MY_SERVICE_DISCOVERY_URL)

  # Call API.
  res = yield my_service.api.greet('John', body={'message': 'hi'})
```

## Creating a service account - guide for admins

See [Pupper service accounts](https://sites.google.com/a/google.com/chrome-infrastructure/systems/puppet/puppet-service-accounts)
