Testing in Infra.git
====================

Testing App Engine with Endpoints
---------------------------------

Writing unit tests for code that uses Google Cloud Endpoints can be difficult.
More precisely, writing the unit tests is much like writing any unit test, but
ensuring that one's unit tests will run can be painful.

Almost ubiquitously, one finds that testing App Engine involves testbed and 
webtest. The former facilitates stubbing of various backend services; the latter
creates a mock application on which one can make API calls and inspect the 
results. Some interactions between Endpoints and webtest may prove turbid even 
to those used to testing App Engine applications; what follows is a series of 
prescriptions concerning the least obvious of these interactions.

Setting up Test Cases Is Subtle Work
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Assume that an Endpoints service is defined as

.. code-block:: python

  @endpoints.api(name='someendpoint', version='v1')
  class SomeEndpoint(remote.Service):
    # <beautiful class definition>
    
This service will be deployed with an invocation like

.. code-block:: python

  app = endpoints.api_server([SomeEndpoint])
  
In test code, one will then have to wrap such an app as a ``webtest.TestApp``, 
taking care to set ``restricted=False``, e.g.

.. code-block:: python

  class MyNiceTestSuite(unittest.TestCase):
  
    def setUp(self):
      
      # <testbed setup, stub initialization, ...>
      app = endpoints.api_server([SomeEndpoint], restricted=False)
      self.source_ip = 'some.ip.address'
      self.test_app = webtest.TestApp(
          app, extra_environ={'REMOTE_ADDR', self.source_ip})
          
With ``restricted=False``, test clients (and other clients from outside Google's
serving infrastructure) can access the server. ``self.source_ip`` is an IP at
which an App Engine instance can be run.

Endpoints Error Handling Has a Known Bug
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Details can be found `here 
<https://code.google.com/p/googleappengine/issues/detail?id=10544>`_.
Essentially, any exceptions raised and not handled during Endpoints code 
execution will be converted within endpoints/apiserving to a JSON response and
served to the client. However, this code does not yet update the 
``Content-Length`` header, so a different error (``AssertionError`` from some 
place in the code that tries to assert that ``Content-Length`` is correct) will 
almost certainly be raised. 

This is easy to fix locally, but, until the bug report is addressed, there 
will be no way to accomplish proper error handling in Endpoints code. For now,
it is recommended to inherit from ``EndpointsTestCase``, found
`here <https://chromium.googlesource.com/infra/swarming/+/master/appengine/components/support/test_case.py>`_,
instead of unittest.TestCase. Among other things (e.g. properly wrapping the 
``endpoints.api_service`` as a ``webtest.TestApp``), this class exposes the 
``call_should_fail`` context manager. While this method is still subject to the 
mentioned bug, it will be more fully implemented pending the bug's resolution. 
The idea will be to assert that the correct error status is raised; one can 
check `this page 
<https://cloud.google.com/appengine/docs/python/endpoints/exceptions>`_ 
for a mapping of Endpoints' exception types to the HTTP status codes they use.
See the example_ below for usage hints. 

Webtest Will Ignore Your API Method's Specifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Let us assume that one has defined the following service and messages:

.. code-block:: python


  class GoodRequest(messages.Message):
    data = messages.IntegerField(1)
    
    
  class GreatReponse(messages.Message):
    data = messages.IntegerField(1)
  
  
  @endpoints.api(name='someendpoint', version='v1')
  class SomeEndpoint(remote.Service):
    
    @endpoints.method(GoodRequest, GreatResponse,
                      path='/exalt', http_method='POST',
                      name='exalt')
    def glorify(self, request):
      response = GreatResponse(data=request.data * request.data)      
      
We define ``SomeEndpoint`` as a subclass of ``remote.Service`` and we give it a 
single method, ``glorify``, which takes ``GoodRequest`` and ``GreatResponse`` 
as its request and response types, respectively. It reads the numeric data 
provided by the request and squares it (the most glorious of arithmetic 
operations). 

We include the pattern in ``app.yaml`` (assuming our Endpoints methods from 
above are in ``something.py`` and that an api_server called "app" is defined 
therein)::

  - url: /_ah/spi/.*
    script: something.app

When we try to test, we find that neither the ``path`` nor the ``name`` will 
avail us, nor can we make calls to ``/_ah/api/<method>``. Instead, the URLs to 
be called in our tests will be of the form 
``/_ah/spi/<ClassName>.<methodname>``. In this example, to test ``glorify``, 
we would make POST requests to ``/_ah/spi/SomeEndpoint.glorify`` completely 
disregarding the ``path`` and ``name`` fields. A little more on this topic can 
be found `here <http://stackoverflow.com/questions/20384743/how-to-unit-test-google-cloud-endpoints>`_.

One final oddity: all API calls will be converted to POST. Thus, whatever 
``http_method`` one declares in the API method definition, one must call 
``self.test_app.post`` (or its analogs, e.g. ``post_json``) when testing the 
API. 

Here Is a Worked Example
~~~~~~~~~~~~~~~~~~~~~~~~

``something.py``, as above, with minor changes:

.. code-block:: python


  class GoodRequest(messages.Message):
    data = messages.IntegerField(1)
    
    
  class GreatReponse(messages.Message):
    data = messages.IntegerField(1)
  
  
  @endpoints.api(name='someendpoint', version='v1')
  class SomeEndpoint(remote.Service):
    
    @endpoints.method(GoodRequest, GreatResponse,
                      path='/exalt', http_method='POST',
                      name='exalt')
    def glorify(self, request):
      glorious_number = request.data
      if glorious_number < 0:
        raise endpoints.BadRequestException(
            'Perhaps you wanted to make a PessimisticRequest?')
      if glorious_number == 109:
        raise endpoints.ForbiddenException(
            'That number is deprecated. Use 28 instead.')    
      response = GreatResponse(data=request.data * request.data)
      
      
We raise two kinds of exceptions: ``endpoints.BadRequestException``, which 
will set the response's status to ``400``, and ``endpoints.ForbiddenException``,
which corresponds to HTTP status ``403``.

.. _example:
``test_something.py``:

.. code-block:: python

  # other imports
  from something import GoodRequest
  from something import GreatResponse
  from something import SomeEndpoint
  

  class MyNiceTestSuite(test_case.EndpointsTestCase):
  
    url = '/_ah/spi/SomeEndpoint.glorify'
  
    def setUp(self):      
      # <testbed setup, stub initialization, ...>
      app = endpoints.api_server([SomeEndpoint], restricted=False)
      self.source_ip = 'some.ip.address'
      self.test_app = webtest.TestApp(
          app, extra_environ={'REMOTE_ADDR', self.source_ip})

    def testGlorifyPerformsWonderfulSquaring(self):
      request = GoodRequest(data=4)
      json_version = json.loads(protojson.encode_message(request))
      response = self.test_app.post_json(self.url, json_version)
      self.assertEquals(response.data, 16)
      
    def testNegativeNumbersAreNotGloriousEnough(self):
      request = GoodRequest(data=-4)
      json_version = json.loads(protojson.encode_message(request))
      with self.call_should_fail('400'):
        response = self.test_app.post_json(self.url, json_version)
        
    def testOneHundredNineIsForbidden(self):
      request = GoodRequest(data=109)
      json_version = json.loads(protojson.encode_message(request))
      with self.call_should_fail('403'):
        response = self.test_app.post_json(self.url, json_version)


Happy testing!

      
