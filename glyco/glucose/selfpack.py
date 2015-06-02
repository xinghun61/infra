# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Packages Glyco as a standalone zip file."""

import os
import zipfile

# Directory containing the glucose package
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def selfpack(args):
  if not args.output_file.endswith('.zip'):
    args.output_file += '.zip'
  print 'Writing output in {}'.format(args.output_file)

  with zipfile.ZipFile(args.output_file, 'w') as f:
    f.write(os.path.join(ROOT_DIR, 'glyco'), '__main__.py')

    def filter_filenames(_current_dir, fnames):
      kept = [fname
              for fname in fnames
              if not (fname.endswith('.pyc') or fname.endswith('~'))
      ]
      return kept


    def add_directory(src, dest):
      """Copy a directory inside the zip file."""
      for dirpath, _, filenames in os.walk(src):
        filenames = filter_filenames(dirpath, filenames)
        reldirpath = os.path.relpath(dirpath, os.path.abspath(src))
        reldirpath = os.path.join(dest, reldirpath)

        for filename in filenames:
          f.write(os.path.join(dirpath, filename),
                  os.path.join(reldirpath, filename))

    # Copy all packages at root level in the zip file
    # TODO(pgervais). Make this process deterministic.
    # https://github.com/luci/luci-py/blob/master/client/utils/zip_package.py\
    # #L196
    add_directory(os.path.join(ROOT_DIR, 'glucose'), 'glucose')
    add_directory(os.path.join(ROOT_DIR, 'third_party'), 'third_party')
  print 'Done.'


def add_subparser(subparsers):
  """Add the 'selfpack' subcommand

  Args:
    subparser: output of argparse.ArgumentParser.add_subparsers()
  """
  parser = subparsers.add_parser('selfpack',
                                 help='Generate a package for Glyco itself.')
  parser.set_defaults(command=selfpack)

  parser.add_argument('--output-file', '-o',
                      help='Output file. A .zip extension is added'
                      ' automatically.',
                      default='glyco.zip')
