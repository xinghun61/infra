Buildbot master authentication to Cloud Endpoints
=================================================

TL;DR Each master may have a service account assigned to it. Two modules
auth.py_ and deferred_resource.py_ together can be used to make authenticated
Cloud Endpoints API calls.

Master service accounts
-----------------------

Each master may have a service account assigned:

.. code-block:: python

    # master_site_config.py
    class MyMaster(Master3):
      # other stuff
      service_account_file = 'service-account-myproject.json'

Service account files should always be named "service-account-[shortname].json".
If ``service_account_file`` attribute is set, ``service_account_path`` attribute
is resolved to ``[CREDENTIALS_DIR]/[service_account_file]``.
In order to request a service account for your master, `file a bug`_.

One service account can be used to authorize calls to different GAE apps.

Service accounts - guide for admins
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Open `chrome-infra-auth app console, credentials page`_. If you can't acccess
   the page, ask vadimsh@chromium.org to grant you a permission, or contact
   infra-dev@chromium.org if Vadim is not available.
2. Press "Create new Client ID" -> "Service account" -> "Create Client ID".
   This will generate a .p12 file.
3. Delete the .p12 file (`shred -fu $filename`).
4. Press "Generate new JSON key" in the appeared service account entry.
5. Delete the first fingerprint in Console. This is a fingerprint for the .p12
   file.
6. Modify puppet config to deploy the json key file to a master machine.

So far, these steps are impossible to automate.

Making authenticated API calls
------------------------------

TL;DR Use deferred_resource.py_ to generate an API client for
Twisted code at runtime. Use auth.py_ to sign it.

.. code-block:: python

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

.. _auth.py: https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/master/auth.py
.. _deferred_resource.py: https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/master/deferred_resource.py
.. _`file a bug`: https://code.google.com/p/chromium/issues/entry?template=Build%20Infrastructure&labels=Infra-Labs,Restrict-View-Google&summary=Service%20account%20[short%20name]%20for%20master.[master_name]&comment=Please%20provide%20a%20service%20account%20json%20key%20file%20%22service-account-[short%20name].json%22%20on%20[master%20machine].%0A%0DInstructions%20for%20admins%20to%20create%20service%20accounts:%20https://sites.google.com/a/google.com/chrome-infrastructure/appspot-instances/buildbot-master-authentication-to-gae-apps
.. _`chrome-infra-auth app console, credentials page`: https://console.developers.google.com/project/chrome-infra-auth/apiui/credential