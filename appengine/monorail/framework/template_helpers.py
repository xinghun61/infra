# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Some utility classes for interacting with templates."""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import cgi
import cStringIO
import httplib
import logging
import time
import types

from third_party import ezt

from protorpc import messages

import settings
from framework import framework_constants


_DISPLAY_VALUE_TRAILING_CHARS = 8
_DISPLAY_VALUE_TIP_CHARS = 120


class PBProxy(object):
  """Wraps a Protocol Buffer so it is easy to acceess from a template."""

  def __init__(self, pb):
    self.__pb = pb

  def __getattr__(self, name):
    """Make the getters template friendly.

    Psudo-hack alert: When attributes end with _bool, they are converted in
    to EZT style bools. I.e., if false return None, if true return True.

    Args:
      name: the name of the attribute to get.

    Returns:
      The value of that attribute (as an EZT bool if the name ends with _bool).
    """
    if name.endswith('_bool'):
      bool_name = name
      name = name[0:-5]
    else:
      bool_name = None

    # Make it possible for a PBProxy-local attribute to override the protocol
    # buffer field, or even to allow attributes to be added to the PBProxy that
    # the protocol buffer does not even have.
    if name in self.__dict__:
      if callable(self.__dict__[name]):
        val = self.__dict__[name]()
      else:
        val = self.__dict__[name]

      if bool_name:
        return ezt.boolean(val)
      return val

    if bool_name:
      # return an ezt.boolean for the named field.
      return ezt.boolean(getattr(self.__pb, name))

    val = getattr(self.__pb, name)

    if isinstance(val, messages.Enum):
      return int(val)  # TODO(jrobbins): use str() instead

    if isinstance(val, messages.Message):
      return PBProxy(val)

    # Return a list of values whose Message entries
    # have been wrapped in PBProxies.
    if isinstance(val, (list, messages.FieldList)):
      list_to_return = []
      for v in val:
        if isinstance(v, messages.Message):
          list_to_return.append(PBProxy(v))
        else:
          list_to_return.append(v)
      return list_to_return

    return val

  def DebugString(self):
    """Return a string representation that is useful in debugging."""
    return 'PBProxy(%s)' % self.__pb

  def __eq__(self, other):
    # Disable warning about accessing other.__pb.
    # pylint: disable=protected-access
    return isinstance(other, PBProxy) and self.__pb == other.__pb


_templates = {}


def GetTemplate(
    template_path, compress_whitespace=True, eliminate_blank_lines=False,
    base_format=ezt.FORMAT_HTML):
  """Make a MonorailTemplate if needed, or reuse one if possible."""
  key = template_path, compress_whitespace, base_format
  if key in _templates:
    return _templates[key]

  template = MonorailTemplate(
      template_path, compress_whitespace=compress_whitespace,
      eliminate_blank_lines=eliminate_blank_lines, base_format=base_format)
  _templates[key] = template
  return template


class cStringIOUnicodeWrapper(object):
  """Wrapper on cStringIO.StringIO that encodes unicode as UTF-8 as it goes."""

  def __init__(self):
    self.buffer = cStringIO.StringIO()

  def write(self, s):
    if isinstance(s, unicode):
      utf8_s = s.encode('utf-8')
    else:
      utf8_s = s
    self.buffer.write(utf8_s)

  def getvalue(self):
    return self.buffer.getvalue()


SNIFFABLE_PATTERNS = {
  '%PDF-': '%NoNoNo-',
}


class MonorailTemplate(object):
  """A template with additional functionality."""

  def __init__(self, template_path, compress_whitespace=True,
               eliminate_blank_lines=False, base_format=ezt.FORMAT_HTML):
    self.template_path = template_path
    self.template = None
    self.compress_whitespace = compress_whitespace
    self.base_format = base_format
    self.eliminate_blank_lines = eliminate_blank_lines

  def WriteResponse(self, response, data, content_type=None):
    """Write the parsed and filled in template to http server."""
    if content_type:
      response.content_type = content_type

    response.status = data.get('http_response_code', httplib.OK)
    whole_page = self.GetResponse(data)
    if data.get('prevent_sniffing'):
      for sniff_pattern, sniff_replacement in SNIFFABLE_PATTERNS.items():
        whole_page = whole_page.replace(sniff_pattern, sniff_replacement)
    start = time.time()
    response.write(whole_page)
    logging.info('wrote response in %dms', int((time.time() - start) * 1000))

  def GetResponse(self, data):
    """Generate the text from the template and return it as a string."""
    template = self.GetTemplate()
    start = time.time()
    buf = cStringIOUnicodeWrapper()
    template.generate(buf, data)
    whole_page = buf.getvalue()
    logging.info('rendering took %dms', int((time.time() - start) * 1000))
    logging.info('whole_page len is %r', len(whole_page))
    if self.eliminate_blank_lines:
      lines = whole_page.split('\n')
      whole_page = '\n'.join(line for line in lines if line.strip())
      logging.info('smaller whole_page len is %r', len(whole_page))
      logging.info('smaller rendering took %dms',
                   int((time.time() - start) * 1000))
    return whole_page

  def GetTemplate(self):
    """Parse the EZT template, or return an already parsed one."""
    # We don't operate directly on self.template to avoid races.
    template = self.template

    if template is None or settings.local_mode:
      start = time.time()
      template = ezt.Template(
          fname=self.template_path,
          compress_whitespace=self.compress_whitespace,
          base_format=self.base_format)
      logging.info('parsed in %dms', int((time.time() - start) * 1000))
      self.template = template

    return template

  def GetTemplatePath(self):
    """Accessor for the template path specified in the constructor.

    Returns:
      The string path for the template file provided to the constructor.
    """
    return self.template_path


class EZTError(object):
  """This class is a helper class to pass errors to EZT.

  This class is used to hold information that will be passed to EZT but might
  be unset. All unset values return None (ie EZT False)
  Example: page errors
  """

  def __getattr__(self, _name):
    """This is the EZT retrieval function."""
    return None

  def AnyErrors(self):
    return len(self.__dict__) != 0

  def DebugString(self):
    return 'EZTError(%s)' % self.__dict__

  def SetError(self, name, value):
    self.__setattr__(name, value)

  def SetCustomFieldError(self, field_id, value):
    # This access works because of the custom __getattr__.
    # pylint: disable=access-member-before-definition
    # pylint: disable=attribute-defined-outside-init
    if self.custom_fields is None:
      self.custom_fields = []
    self.custom_fields.append(EZTItem(field_id=field_id, message=value))

  any_errors = property(AnyErrors, None)

def FitUnsafeText(text, length):
  """Trim some unsafe (unescaped) text to a specific length.

  Three periods are appended if trimming occurs. Note that we cannot use
  the ellipsis character (&hellip) because this is unescaped text.

  Args:
    text: the string to fit (ASCII or unicode).
    length: the length to trim to.

  Returns:
    An ASCII or unicode string fitted to the given length.
  """
  if not text:
    return ""

  if len(text) <= length:
    return text

  return text[:length] + '...'


def BytesKbOrMb(num_bytes):
  """Return a human-readable string representation of a number of bytes."""
  if num_bytes < 1024:
    return '%d bytes' % num_bytes  # e.g., 128 bytes
  if num_bytes < 99 * 1024:
    return '%.1f KB' % (num_bytes / 1024.0)  # e.g. 23.4 KB
  if num_bytes < 1024 * 1024:
    return '%d KB' % (num_bytes / 1024)  # e.g., 219 KB
  if num_bytes < 99 * 1024 * 1024:
    return '%.1f MB' % (num_bytes / 1024.0 / 1024.0)  # e.g., 21.9 MB
  return '%d MB' % (num_bytes / 1024 / 1024)  # e.g., 100 MB


class EZTItem(object):
  """A class that makes a collection of fields easily accessible in EZT."""

  def __init__(self, **kwargs):
    """Store all the given key-value pairs as fields of this object."""
    vars(self).update(kwargs)

  def __repr__(self):
    fields = ', '.join('%r: %r' % (k, v) for k, v in
                       sorted(vars(self).iteritems()))
    return '%s({%s})' % (self.__class__.__name__, fields)


def ExpandLabels(page_data):
  """If page_data has a 'labels' list, expand it into 'label1', etc.

  Args:
    page_data: Template data which may include a 'labels' field.
  """
  label_list = page_data.get('labels', [])
  if isinstance(label_list, types.StringTypes):
    label_list = [label.strip() for label in page_data['labels'].split(',')]

  for i in range(len(label_list)):
    page_data['label%d' % i] = label_list[i]
  for i in range(len(label_list), framework_constants.MAX_LABELS):
    page_data['label%d' % i] = ''


class TextRun(object):
  """A fragment of user-entered text that needs to be safely displyed."""

  def __init__(self, content, tag=None, href=None):
    self.content = content
    self.tag = tag
    self.href = href
    self.title = None
    self.css_class = None
