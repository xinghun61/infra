====================
Testing in Infra.git
====================

The Bare Minimum
----------------
All operations on tests are performed using the ``test.py`` script located at
the root of the repository. Here are some commands for the impatient:

+-----------------------------------------+-------------------------------------+
| ``./test.py test``                      | Run all tests in the repository and |
|                                         | report results.                     |
+-----------------------------------------+-------------------------------------+
| ``./test.py list``                      | List all tests in the repository,   |
|                                         | without running them.               |
+-----------------------------------------+-------------------------------------+
| ``./test.py test infra``                | Run only tests found in the         |
|                                         | infra package.                      |
+-----------------------------------------+-------------------------------------+
| ``./test.py train``                     | Run all tests and write             |
|                                         | expectations.                       |
+-----------------------------------------+-------------------------------------+
| ``./test.py test infra:*foo*``          | Run tests from infra with           |
|                                         | 'foo' in their name.                |
+-----------------------------------------+-------------------------------------+

By default, ``test.py`` collects coverage information, and not having 100%
coverage is an error.


Writing Tests
-------------
``test.py`` enforces some constraints so as to maintain a clear structure in
the repository. Namely:

- tests must be methods of subclasses of unittest.TestCase. test.py will *not*
  look for standalone functions. In addition, the method name must start with
  'test'.
- tests classes must be contained in files named like ``*_test.py``.
- the coverage information for file ``foo.py`` is only collected from tests
  located in ``test/foo_test.py`` or ``tests/foo_test.py``.

A test fails when an exception is raised, or if expectations don't match (read
on). Test methods can return a value. When run in train mode, ``test.py``
stores these values on disk, in directories named like ``*.expected/`` next to
the file containing tests. When run in test mode, the return values are compared
to the ones previously stored, and the test fails if they don't match.

:Example:

.. code-block:: python

  import unittest
  import

  class FooTest(unittest.TestCase):
    def test_sha1(self):
      ret = hashlib.sha1("Unimportant text").hexdigest()
      self.assertEqual(ret, '19c12dd68b216f1a7a26d5b0290355ceef8a35b2')

    def test_sha1_expectations(self):
      ret = hashlib.sha1("Unimportant text").hexdigest()
      return ret


``test_sha1`` and ``test_sha1_expectations`` performs the same task, in a
different way. To have both tests pass, you have to run::

  ./test.py train   # record output of test_sha1_expectations
  ./test.py test


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

For a more detailed description of the system, adapted to the novice and with
pointers to enlightening reading, see :doc:`testing_novice`.
For high-level documentation intended for the seasoned App Engine/Cloud
Endpoints developer, read on.

A Worked Example
~~~~~~~~~~~~~~~~~~~~~~~~

``something.py`` contains the API:

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
      response = GreatResponse(data=request.data ** 2)

``test/something_test.py`` contains our test suite:

.. code-block:: python

  # other imports
  from something import SomeEndpoint
  from support import test_case


  class MyNiceTestSuite(test_case.EndpointsTestCase):

    api_service_cls = SomeEndpoint

    def setUp(self):
      super(MyNiceTestSuite, self).setUp()
      # testbed setup, stub initialization, etc. should go here

    def testGlorifyPerformsWonderfulSquaring(self):
      request = {'data': 4}
      response = self.call_api('glorify', request).json_body
      self.assertEquals(response, {'data': 16})

    def testNegativeNumbersAreNotGloriousEnough(self):
      request = {'data': -4}
      with self.call_should_fail('400'):
        _ = self.call_api('glorify', request)

test_case.EndpointsTestCase Is Balm to One Parched
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`This module <https://chromium.googlesource.com/infra/swarming/+/master/appengine/components/support/test_case.py>`_
hides some of the complexity of writing test cases for Endpoints code. To
explicate, ``EndpointsTestCase`` provides the following facilities:

- explicit creation of ``endpoints.api_server`` and ``webtest.testApp``
  with ``setUp``
- correct routing to endpoints methods (the user no longer needs to write
  ``'/_ah/spi/IncredibleEndpointName.someLongMethodName'``) with ``call_api``
- error management (which will become error handling pending a fix for
  `this bug <https://code.google.com/p/googleappengine/issues/detail?id=10544>`_)
  with ``call_should_fail``

Much of the obscurity in Endpoints testing now evaporates. By using
``EndpointsTestCase``, we avoid the pitfalls that inhere in setting up and
posting to such an API in a test environment. A few final points:

- ``api_service_cls``, a class member of the test suite, must be set; otherwise,
  the test suite will not be able to create a test application and will not
  have any knowledge of the API's methods
- ``EndpointsTestCase.call_api`` and ``EndpointsTestCase.call_should_fail`` are
  the recommended ways to make an API call and to handle errors, respectively.
  Note that the argument structure for call_api is (<method name>, <request
  body>); the method name is literally the name to which a method is bound in
  the API code, not the name specified in the decorator

Happy testing!
