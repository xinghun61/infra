# Testing with Endpoints 101

This document assumes familiarity with writing Endpoints APIs in Python
and with App Engine testing. The intention is to follow one path toward
baseline App Engine and Endpoints testing knowledge, saving one hours/days
searching for solutions to the non-trivial problems which may
arise. Edifying links can be found throughout.

Users already comfortable with Endpoints (or just in need of
plug-and-play example code) can skip to
Conclusion: Use `test_case.EndpointsTestCase` or return to
[Testing](testing.md).

## Introduction: Setting up Test Cases Is Subtle Work

Assume that an Endpoints service is defined as

```python
class QuietRequest(messages.Message):
  whispered = messages.StringField(1)


class LoudReponse(messages.Message):
  yelled = messages.StringField(1)


@endpoints.api(name='someendpoint', version='v1')
class UpToElevenEndpoint(remote.Service):

  @endpoints.method(QuietRequest, LoudResponse,
                    path='/fortissimo', http_method='POST',
                    name='fortissimo')
  def yell(self, request):
    response = LoudResponse(yelled=request.whispered.upper())
```

This service will be deployed with an invocation like

```python
app = endpoints.api_server([UpToElevenEndpoint])
```

In test code, one would then have to wrap such an app as a
`webtest.TestApp`, taking care to set `restricted=False`, e.g.

```python
class VolumeTestSuite(unittest.TestCase):

  def setUp(self):
    super(VolumeTestSuite, self).setUp()
    # testbed setup, stub initialization, etc. should go here
    app = endpoints.api_server([UpToElevenEndpoint], restricted=False)
    self.source_ip = 'some.ip.address'
    self.test_app = webtest.TestApp(
        app, extra_environ={'REMOTE_ADDR', self.source_ip})

  def testYellMethod(self):
    response = self.test_app.post_json(
        '/_ah/spi/UpToElevenEndpoint.yell', {'whispered': 'yes, I am data'})
    self.assertEqual(
        json.loads(response.body).get('yelled', ''), 'YES, I AM DATA')
```

With `restricted=False`, test clients (and other clients from outside
Google's serving infrastructure) can access the server. `self.source_ip`
is an IP at which an App Engine instance can be run.

If questions have arisen for you about any of the above, it may be
beneficial to read on; if not, the punchline lies at
Conclusion: Use `test_case.EndpointsTestCase`.

### Quirk the First: Webtest Will Ignore Your API Method's Specifications

Let us assume that one has defined the following service and messages in
file `something.py`:

```python
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
    response = GreatResponse(data=request.data ** 2)
```

We define `SomeEndpoint` as a subclass of `remote.Service` and we give
it a single method, `glorify`, which takes `GoodRequest` and
`GreatResponse` as its request and response types, respectively. It
reads the numeric data provided by the request and squares it (the most
glorious of arithmetic operations).

We include the pattern in `app.yaml` (assuming our Endpoints methods
from above are in `something.py` and that an `api_server` called `app` is
defined therein):

```yaml
- url: /_ah/spi/.*
  script: something.app
```

When we try to test on a local dev server, we find that neither `path`
nor `name` will avail us, nor can we make calls to `/_ah/api/<method>`.
Instead, the URLs to be called in our tests will be of the form
`/_ah/spi/<ClassName>.<methodname>`. In this example, to test `glorify`,
we would make POST requests to `/_ah/spi/SomeEndpoint.glorify`,
completely disregarding the `path` and `name` fields. A little more on
this topic can be found
[here](http://stackoverflow.com/questions/20384743/how-to-unit-test-google-cloud-endpoints).

One final oddity: all API calls will be converted to POST. Thus,
whatever `http_method` one declares in the API method definition, one
must call `self.test_app.post` (or its analogs, e.g. `post_json`) when
testing the API.

### Quirk the Second: Endpoints Error Handling Has a Known Bug

Details can be found
[here](https://code.google.com/p/googleappengine/issues/detail?id=10544).
Essentially, any exceptions raised and not handled during Endpoints code
execution will be converted within endpoints/apiserving to a JSON
response and served to the client. However, this code does not yet
update the `Content-Length` header, so a different error
(`AssertionError` from some place in the code that tries to assert that
`Content-Length` is correct) will almost certainly be raised.

This is easy to fix locally, but, until the bug report is addressed,
there will be no way to accomplish proper error handling in Endpoints
code.

#### Error Example

Let's add error cases to `something.py`:

```python
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
    response = GreatResponse(data=request.data ** 2)
```

We raise two kinds of exceptions: `endpoints.BadRequestException`, which
will set the response's status to `400`, and
`endpoints.ForbiddenException`, which corresponds to HTTP status `403`.
One can check [this
page](https://cloud.google.com/appengine/docs/python/endpoints/exceptions)
for a mapping of Endpoints' exception types to the HTTP status codes
they use.

We would expect to be able to add code like

```python
with self.assertRaises(endpoints.ForbiddenException):
  response = self.test_app.post_json(
      '/_ah/spi/SomeEndpoint.glorify', {'data': 109})
```

or manually check that the status code in the response is `403`;
however, either method will yield the rather cryptic
`AppError: Bad response: 500 Internal Server Error (not 200)` due to the
content-length problem described above.

#### Solution

It is thus recommended to inherit from
[EndpointsTestCase](https://chromium.googlesource.com/infra/swarming/+/master/appengine/components/support/test_case.py),
instead of `unittest.TestCase`. Among other things (e.g. properly wrapping
the `endpoints.api_service` as a `webtest.TestApp`), this class exposes
the `call_should_fail` context manager. While this method is still
subject to the mentioned bug, it will be more fully implemented pending
the bug's resolution. One simply asserts that the correct error status
is raised, e.g.

```python
with self.call_should_fail('403'):
  response = self.test_app.post_json(
      '/_ah/spi/SomeEndpoint.glorify', {'data': 109})
```

## Conclusion: Use `test_case.EndpointsTestCase`

The previous section gestured toward a test module that addresses some
of the shortcomings concerning Endpoints testing. In fact, much of the
above complexity can be circumvented by using
[`test_case` module](https://chromium.googlesource.com/infra/swarming/+/master/appengine/components/support/test_case.py).
For more on EndpointsTestCase, return to [testing](testing.md).
