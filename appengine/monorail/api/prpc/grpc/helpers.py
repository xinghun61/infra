import base64
import copy
import json
import re

from google.protobuf import json_format, text_format


class Encoding(object):
  BINARY = (0, 'application/prpc; encoding=binary')
  JSON   = (1, 'application/prpc; encoding=json')
  TEXT   = (2, 'application/prpc; encoding=text')

  @staticmethod
  def header(encoding):
    return encoding[1]


def _parse_media_type(media_type):
  if media_type is None:
    return Encoding.BINARY
  if media_type == 'application/prpc; encoding=binary':
    return Encoding.BINARY
  if media_type == 'application/prpc; encoding=json':
    return Encoding.JSON
  if media_type == 'application/json':
    return Encoding.JSON
  if media_type == 'application/prpc; encoding=text':
    return Encoding.TEXT
  raise ValueError('Invalid media type "%s"' % media_type)


def _parse_timeout(timeout):
  if timeout is None:
    return None
  header_re = r'^(?P<amount>\d+)(?P<units>[HMSmun])$'
  m = re.match(header_re, timeout)
  if m is None:
    raise ValueError('Incorrectly formatted timeout header')
  if m.group('units') == 'H':
    multiplier = 60*60
  elif m.group('units') == 'M':
    multiplier = 60
  elif m.group('units') == 'S':
    multiplier = 1
  elif m.group('units') == 'm':
    multiplier = 0.001
  elif m.group('units') == 'u':
    multiplier = 1e-6
  elif m.group('units') == 'n':
    multiplier = 1e-9
  else:
    raise ValueError('Incorrectly formatted timeout header')
  seconds = int(m.group('amount')) * multiplier
  return seconds


def process_headers(context, headers):
  """Parses headers and sets up the context object.

  Args:
    context: a types.ServicerContext
    headers: the self.request.headers dict from a webapp2.RequestHandler

  Returns:
    content_type: an Encoding enum value for the incoming request
    accept: an Encoding enum value for the outgoing response

  Raises:
    ValueError: when the headers indicate invalid content types or don't parse
  """
  content_type_header = headers.get('Content-Type')
  try:
    content_type = _parse_media_type(content_type_header)
  except ValueError:
    # TODO(agable): Figure out why the development server is getting the
    # header with an underscore instead of a hyphen for some requests.
    content_type_header = headers.get('Content_Type')
    if content_type_header:
      content_type = _parse_media_type(content_type_header)

  accept_header = headers.get('Accept')
  # TODO(agable): Correctly parse accept headers that are more complex (e.g.
  # list multiple acceptable types, or have quality factors).
  accept = _parse_media_type(accept_header)

  timeout_header = headers.get('X-Prpc-Timeout')
  context.timeout = _parse_timeout(timeout_header)

  for header, value in headers.iteritems():
    if header.endswith('-Bin'):
      try:
        value = base64.b64decode(value)
      except TypeError:
        raise ValueError('Received invalid base64 string in header %s' % header)
      header = header[:-len('-Bin')]
    if header in context.invocation_metadata:
      raise ValueError('Received multiple values for header %s' % header)
    context.invocation_metadata[header] = value

  return content_type, accept


def get_decoder(encoding):
  """Returns the appropriate decoder for content type.

  Args:
    encoding: A value from the Encoding enum

  Returns:
    a callable which takes an encoded string and an empty protobuf message, and
        populates the given protobuf with data from the string. Each decoder
        may raise exceptions of its own based on incorrectly formatted data.
  """
  if encoding == Encoding.BINARY:
    return lambda string, proto: proto.ParseFromString(string)
  elif encoding == Encoding.JSON:
    return json_format.Parse
  elif encoding == Encoding.TEXT:
    return text_format.Merge
  else:
    assert False, 'Argument |encoding| was not a value of the Encoding enum.'


def get_encoder(encoding):
  """Returns the appropriate encoder for the Accept content type.

  Args:
    encoding: A value from the Encoding enum

  Returns:
    a callable which takes an initialized protobuf message, and returns a string
        representing its data. Each encoder may raise exceptions of its own.
  """
  if encoding == Encoding.BINARY:
    return lambda proto: proto.SerializeToString()
  elif encoding == Encoding.JSON:
    return lambda proto: ')]}\'' + json_format.MessageToJson(proto)
  elif encoding == Encoding.TEXT:
    return lambda proto: text_format.MessageToString(proto, as_utf8=True)
  else:
    assert False, 'Argument |encoding| was not a value of the Encoding enum.'
