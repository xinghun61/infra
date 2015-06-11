# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import os

# infra subdirectory containing tools.
TOOL_DIR = os.path.dirname(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')

COPYRIGHT_NOTICE = """\
# Copyright %s The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
""" % datetime.datetime.now().strftime('%Y')


def add_argparse_options(parser):
  parser.add_argument(
      'name', metavar='name', type=str, nargs=1,
      help='The name of the new tool.')

  parser.add_argument('--base-dir', default=TOOL_DIR,
                      help='Directory where to create the tool. Default: '
                      '%(default)s')


def generate_python_file(dirpath, filename, template,
                         template_dir=TEMPLATE_DIR, **kwargs):
  """Generate a python file based on a template.

  This function does nothing if the target file already exists.

  Args:
    dirpath (str): directory where to create the file.
    filename (str): base name of file to generate.
    template (str): name of the template file (without extension)

  Keywords Args:
    template_dir (str): path to the directory where templates are stored.
    kwargs (dict): passed to the template.

  Return:
    filename (str): path to the file that has been generated.
  """
  file_path = os.path.join(dirpath, filename + '.py')
  if os.path.isfile(file_path):
    print 'Skipping existing file %s' % file_path
    return file_path

  if template:
    with open(os.path.join(template_dir, template + '.template'), 'r') as f:
      MAIN_CONTENT = f.read().format(**kwargs)
  else:
    MAIN_CONTENT = ''

  with open(file_path, 'w') as f:
    f.write(COPYRIGHT_NOTICE)
    f.write(MAIN_CONTENT)
  return file_path


def generate_tool_files(toolname, base_dir):
  """Generate a stub tool from template files.

  Args:
    toolname (str): name of the tool. This is also the name of the directory
      generated.
    base_dir (str): path to the directory where to create the files.

  Return:
    tool_path (str or None): directory created or None is nothing has been done.
  """

  if not os.path.isdir(base_dir):
    print 'Destination directory does not exist'
    return 1

  tool_dir = os.path.join(base_dir, toolname)
  if os.path.exists(tool_dir):
    print 'Tool seems to already exists: %s\nAborting.' % tool_dir
    return 1

  print 'Generating %s...' % tool_dir
  os.mkdir(tool_dir)
  generate_python_file(tool_dir, '__init__', None)
  generate_python_file(tool_dir, '__main__', 'main',
                       toolname=toolname,
                       Toolname=toolname.capitalize())
  generate_python_file(tool_dir, toolname, 'tool',
                       Toolname=toolname.capitalize())

  test_dir = os.path.join(tool_dir, 'test')
  os.mkdir(test_dir)
  generate_python_file(test_dir, '__init__', None)
  generate_python_file(test_dir, toolname + '_test', 'test',
                       toolname=toolname,
                       tested_file=toolname)
  print 'Done.'
