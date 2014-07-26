# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from cStringIO import StringIO


class _Invalid(object):
  def __call__(self, *_args, **_kwargs):
    return self

  def __getattr__(self, _key):
    return self

  def __eq__(self, _other):
    return False

  def __ne__(self, _other):  # pylint: disable=R0201
    return True

INVALID = _Invalid()


class CalledProcessError(Exception):
  """Almost like subprocess.CalledProcessError, but also captures stderr,
  and gives prettier error messages.
  """
  def __init__(self, returncode, cmd, stdout, stderr):
    super(CalledProcessError, self).__init__()
    self.returncode = returncode
    self.cmd = cmd
    self.stdout = stdout
    self.stderr = stderr

  def __str__(self):
    msg = StringIO()

    suffix = ':' if self.stderr or self.stdout else '.'
    print >> msg, (
        "Command %r returned non-zero exit status %d%s"
        % (self.cmd, self.returncode, suffix)
    )

    def indent_data(banner, data):
      print >> msg, banner, '=' * 40
      msg.writelines('  ' + l for l in data.splitlines(True))

    if self.stdout:
      indent_data('STDOUT', self.stdout)

    if self.stderr:
      if self.stdout:
        print >> msg
      indent_data('STDERR', self.stderr)

    r = msg.getvalue()
    if r[-1] != '\n':
      r += '\n'
    return r

