# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Generate a new AppEngine app folder in infra/appengine/."""

import argparse
import datetime
import os
import sys
import textwrap


INFRA_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
APPENGINE_DIR = os.path.join(INFRA_ROOT, 'appengine' )
COPYRIGHT_NOTICE = textwrap.dedent("""\
    # Copyright %s The Chromium Authors. All rights reserved.
    # Use of this source code is governed by a BSD-style license that can be
    # found in the LICENSE file.
    """) % datetime.datetime.now().strftime('%Y')


def main(argv):
  parser = argparse.ArgumentParser(description=sys.modules['__main__'].__doc__)
  parser.add_argument(
      'name', metavar='name', type=str, nargs=1,
      help='The name of the new AppEngine folder.')

  args = parser.parse_args(argv)

  app_dir = os.path.join(APPENGINE_DIR, args.name[0])
  return create_app(app_dir)


def create_app(app_dir):
  test_dir = os.path.join(app_dir, 'test')

  print 'Creating %s...' % app_dir

  try:
    os.mkdir(app_dir)
  except OSError:
    print 'Oops, looks like such app already exists: %s.' % app_dir
    return 1

  os.symlink('../../appengine_module/expect_tests_pretest.py',
             os.path.join(app_dir, '.expect_tests_pretest.py'))
  os.symlink('../../appengine_module/testing_utils',
             os.path.join(app_dir, 'testing_utils'))
  os.symlink('../../luci/appengine/components/components',
             os.path.join(app_dir, 'components'))
  os.symlink('../../luci/appengine/components/tools/gae.py',
             os.path.join(app_dir, 'gae.py'))

  expect_tests_cfg = os.path.join(app_dir, '.expect_tests.cfg')

  with open(expect_tests_cfg, 'w') as f:
    f.write(textwrap.dedent("""\
        [expect_tests]
        skip=components
        """))

  with open(os.path.join(app_dir, 'app.yaml'), 'w') as f:
    f.write(textwrap.dedent("""\
        runtime: python27
        api_version: 1
        threadsafe: true

        # Edit this to match your implementation.
        handlers:
        - url: /.*
          secure: always
          script: main.app

        libraries:
        - name: endpoints
          version: 1.0
        - name: jinja2
          version: latest
        - name: pycrypto
          version: "2.6"
        - name: webapp2
          version: latest
        - name: webob
          version: "1.2.3"

        includes:
        - components/auth
        """))

  with open(os.path.join(app_dir, 'main.py'), 'w') as f:
    f.write(textwrap.dedent("""\
        %s

        import webapp2

        from components import auth


        class MainHandler(auth.AuthenticatingHandler):
          @auth.public
          def get(self):
            self.response.write('Hello world!')


        main_handlers = [
              (r'/', MainHandler),
        ]

        app = webapp2.WSGIApplication(main_handlers, debug=True)
        """) % COPYRIGHT_NOTICE)

  os.mkdir(test_dir)
  with open(os.path.join(test_dir, '__init__.py'), 'w') as f:
    f.write(COPYRIGHT_NOTICE)

  with open(os.path.join(test_dir, 'main_test.py'), 'w') as f:
    f.write(textwrap.dedent("""\
        %s

        import logging

        from testing_utils import testing

        import main


        class MainTest(testing.AppengineTestCase):
          @property
          def app_module(self):
            return main.app

          def test_get(self):
            response = self.test_app.get('/')
            logging.info('response = %%s', response)
            self.assertEquals(200, response.status_int)
        """) % COPYRIGHT_NOTICE)

  print 'Created successfully.'
  print 'Edit %s\nif you add third party components.' % expect_tests_cfg
  print
  print 'Found a bug? Got a feature request? Please visit go/chrome-infra-bug.'


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
