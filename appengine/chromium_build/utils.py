
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utils."""

import re
import time
import random
import logging
import sys
import string
import json
import urllib

from google.appengine.api import users


def admin_only(func):
  """Valid for BasePage objects only."""
  def decorated(self, *args, **kwargs):
    if self.is_admin:
      return func(self, *args, **kwargs)
    else:
      self.response.headers['Content-Type'] = 'text/plain'
      self.response.out.write('Forbidden')
      self.error(403)
  return decorated


def clean_int(value, default):
  """Convert a value to an int, or the default value if conversion fails."""
  try:
    return int(value)
  except (TypeError, ValueError):
    return default


def require_user(func):
  """A user must be logged in."""
  def decorated(self, *args, **kwargs):
    if not self.user:
      self.redirect(users.create_login_url(self.request.url))
    else:
      return func(self, *args, **kwargs)
  return decorated


############
# Decorators
############

def render(template_filename, jinja_environment):
  """Use a template to render results.  The wrapped function is expected to
  return a dict."""
  def _render(fn):
    def wrapper(self, *args, **kwargs):
      results = fn(self, *args, **kwargs)
      template = jinja_environment.get_template(template_filename)
      self.response.out.write(template.render(results))
    return wrapper
  return _render


def render_iff_new_flag_set(template_filename, jinja_environment):
  """Use the given template if and only if the 'new' flag is set by:
  * The presence of the 'new' cookie.
  * 'new' is passed in as an url parameter."""
  def _render(fn):
    def wrapper(self, *args, **kwargs):
      new = self.request.get('new') or self.request.cookies.get('new')
      use_json = self.request.get('json')
      kwargs.update({'new': new})
      results = fn(self, *args, **kwargs)
      if new:
        if use_json:
          self.response.out.write(json.dumps(results))
          return
        template = jinja_environment.get_template(template_filename)
        try:
          self.response.out.write(template.render(results))
        except Exception as e:
          logging.error('Caught exception while calling %s with template %s' %
                        (self.__class__.__name__, template_filename))
          raise e, None, sys.exc_info()[2]
      else:
        # Just treat the results as a large string blob.
        self.response.out.write(results)
    return wrapper
  return _render


def render_json(fn):
  """The function is expected to return a dict, and we want to render json."""
  def wrapper(self, *args, **kwargs):
    results = fn(self, *args, **kwargs)
    self.response.out.write(json.dumps(results))
  return wrapper


def maybe_render_json(template_filename, jinja_environment):
  """If the variable 'json' exists in the request, return a json object.
  Otherwise render the page using the template"""
  def _render(fn):
    def wrapper(self, *args, **kwargs):
      results = fn(self, *args, **kwargs)
      if self.request.get('json'):
        self.response.out.write(json.dumps(results))
      else:
        template = jinja_environment.get_template(template_filename)
        self.response.out.write(template.render(results))
    return wrapper
  return _render


def login_required(fn):
  """Redirect user to a login page."""
  def wrapper(self, *args, **kwargs):
    user = users.get_current_user()
    if not user:
      self.redirect(users.create_login_url(self.request.uri))
      return
    else:
      return fn(self, *args, **kwargs)
  return wrapper


def google_login_required(fn):
  """Return 403 unless the user is logged in from a @google.com domain."""
  def wrapper(self, *args, **kwargs):
    user = users.get_current_user()
    if not user:
      self.redirect(users.create_login_url(self.request.uri))
      return
    email_match = re.match('^(.*)@(.*)$', user.email())
    if email_match:
      _, domain = email_match.groups()
      if domain == 'google.com':
        return fn(self, *args, **kwargs)
    self.error(403)  # Unrecognized email or unauthroized domain.
    self.response.out.write('unauthroized email %s' % user.user_id())
  return wrapper


def admin_required(fn):
  """Return 403 unless an admin is logged in."""
  def wrapper(self, *args, **kwargs):
    user = users.get_current_user()
    if not user:
      self.redirect(users.create_login_url(self.request.uri))
      return
    elif not users.is_current_user_admin():
      self.error(403)
      return
    else:
      return fn(self, *args, **kwargs)
  return wrapper


def expect_request_param(*request_args):
  """Strips out the expected args from a request and feeds it into the function
  as the arguments.  Optionally, typecast the argument from a string into a
  different class.  Examples include:
  name                  (Get the request object called "name")
  time as timestamp     (Get "time", pass it in as "timestamp")
  """
  def _decorator(fn):
    def wrapper(self, *args, **kwargs):
      request_kwargs = {}
      for arg in request_args:
        # TODO(hinoka): Optional typecasting?
        arg_match = re.match(r'^(\((\w+)\))?\s*(\w+)( as (\w+))?$', arg)
        if arg_match:
          _, _, name, _, target_name = arg_match.groups()
          if not target_name:
            target_name = name
          request_item = self.request.get(name)
          request_kwargs[target_name] = request_item
        else:
          raise Exception('Incorrect format %s' % arg)
      kwargs.update(request_kwargs)
      return fn(self, *args, **kwargs)
    return wrapper
  return _decorator


###############
# Jinja filters
###############

def delta_time(delta):
  hours = int(delta/60/60)
  minutes = int((delta - hours * 3600)/60)
  seconds = int(delta - (hours * 3600) - (minutes * 60))
  result = ''
  if hours:
    result += '%d hr' % hours
  if minutes:
    if hours:
      result += ', '
    result += '%d min' % minutes
  if not hours:
    if hours or minutes:
      result += ', '
    result += '%d sec' % seconds
  return result


def time_since(timestamp):
  delta = time.time() - timestamp
  return delta_time(delta)


def nl2br(value):
  return value.replace('\n','<br>\n')


def rot13_email(value):
  nonce = ''.join(random.choice(
      string.ascii_uppercase + string.digits) for x in range(6))
  rep = ('<span id="obf-%s"><script>document.getElementById("obf-%s").'
         'innerHTML="<n uers=\\"znvygb:%s\\" gnetrg=\\"_oynax\\">%s</n>".'
         'replace(/[a-zA-Z]/g,function(c){return String.fromCharCode(('
         'c<="Z"?90:122)>=(c=c.charCodeAt(0)+13)?c:c-26);});</script>'
         '<noscript><span style="unicode-bidi:bidi-override;direction:rtl;"'
         '>%s</span></noscript></span>')
  return rep % (nonce, nonce, value.encode('rot13'),
      value.encode('rot13'), value[::-1])


def _blockquote(value):
  """Wrap blockquote levels recursively."""
  new_value = ''
  blockquote = False
  for line in value.splitlines():
    if blockquote:
      if line.startswith('>'):
        new_value += '%s\n' % line[1:].strip()
      else:
        blockquote = False
        new_value += '</blockquote>%s\n' % line
    else:
      if line.startswith('>'):
        blockquote = True
        new_value += '<blockquote>%s\n' % line[1:].strip()
      else:
        new_value += '%s\n' % line
  if blockquote:
    new_value += '</blockquote>'
  if re.search(r'^>', new_value, re.M):
    return _blockquote(new_value)
  else:
    return new_value


def _resolve_crbug(match):
  results = []
  bugs = match.group(1).split(',')
  for bug in bugs:
    results.append('<a href="http://crbug.com/%s">%s</a>' % (bug, bug))
  return 'BUG=%s' % ','.join(results)


def cl_comment(value):
  """Add links to https:// addresses, BUG=####, and trim excessive newlines."""
  value = re.sub(r'(https?://.*)', r'<a href="\1">\1</a>', value)
  value = re.sub(r'BUG=([\d,]+)', _resolve_crbug, value)
  # Add blockquotes.
  value = _blockquote(value)
  value = re.sub(r'\n', r'<br>', value)
  # Obfuscure email addresses with rot13 encoding.
  value = re.sub(r'(\w+@[\w.]+)', lambda m: rot13_email(m.group(1)), value)
  return value

def urlquote(value, safe=''):
  return urllib.quote(value, safe=safe)
