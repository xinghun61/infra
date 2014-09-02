import PRESUBMIT

import unittest
import re
import os


# There is a MockInputAPI in depot_tools/presubmit_unittest.py
# but it doesn't have a fake in-memory file system, which is useful. :)
# This is modeled after webkitpy's much more complete MockFileSystem:
# pylint: disable=C0301
# http://trac.webkit.org/browser/trunk/Tools/Scripts/webkitpy/common/system/filesystem_mock.py
class MockFileSystem(object):
  """A mock for os.walk as well as os.path for MockInputAPI"""

  pathsep = '/'

  def __init__(self, files=None, cwd=None):
    self.cwd = cwd or '/mock'
    # MockFileSystem allows files to have contents, we don't need that though.
    self.files = map(self.abspath, files) if files else []
    self.dirs = set([])
    for f in self.files:
      d = self.dirname(f)
      while not d in self.dirs:
        self.dirs.add(d)
        d = self.dirname(d)

  def normpath(self, path):
    return re.sub(re.escape(os.path.sep), self.pathsep, os.path.normpath(path))

  def abspath(self, path):
    if os.path.isabs(path):
      return self.normpath(path)
    return self.abspath(self.join(self.cwd, path))

  # This is modified from WebKit's which has a bug that
  # dirname('/') == '' which was wrong.
  def dirname(self, path):
    if self.pathsep not in path:
      return ''
    parts = path.rsplit(self.pathsep, 1)
    if not parts[0]:
      return self.pathsep # Is this right on windows?
    return parts[0]

  def isfile(self, path):
    return self.abspath(path) in self.files

  # FIXME: This should probably use normpath(path), but we don't have normpath.
  def isdir(self, path):
    return self.abspath(path) in self.dirs

  def exists(self, path):
    return self.isfile(path) or self.isdir(path)

  def join(self, *comps):
    # Slow, but will work on windows, regardless of self.pathsep.
    # See WebKit's MockFilesSystem for something faster.
    return re.sub(re.escape(os.path.sep), self.pathsep, os.path.join(*comps))

  # Not the same as os.walk, but close enough to work.
  def walk(self, top):
    sep = self.pathsep
    if not self.isdir(top):  # pragma: no cover
      raise OSError("%s is not a directory" % top)

    if not top.endswith(sep):  # pragma: no cover
      top += sep

    dirs = []
    files = []
    for f in self.files:
      if self.exists(f) and f.startswith(top):
        remaining = f[len(top):]
        if sep in remaining:
          dir_name = remaining[:remaining.index(sep)]
          if not dir_name in dirs:
            dirs.append(dir_name)
        else:
          files.append(remaining)

    yield top[:-1], dirs, files

    for name in dirs:
      for result in self.walk(self.join(top, name)):
        yield result


class MockLogging(object):
  @staticmethod
  def info(ignored):
    pass


class MockInputAPI(object):
  def __init__(self, files=None):
    mock_fs = MockFileSystem(files)
    self.os_path = mock_fs
    self.os_walk = mock_fs.walk
    self.re = re
    self.environ = {}
    self.logging = MockLogging()


  @staticmethod
  def PresubmitLocalPath():
    return '/mock'


class PresubmitTest(unittest.TestCase):
  def test_GroupPythonFilesByRoot(self):
    files = [
      'PRESUBMIT.py',
      'bootstrap/foo.py',
      'infra/__init__.py',
      'infra/bar/__init__.py',
      'infra/bar/baz.py',
      'infra/foo.py',
    ]
    input_api = MockInputAPI(files)
    expected_groups = {
      '': ['PRESUBMIT.py'],
      'bootstrap': ['bootstrap/foo.py'],
      'infra': [
        'infra/__init__.py',
        'infra/bar/__init__.py',
        'infra/bar/baz.py',
        'infra/foo.py',
      ],
    }
    grouped_paths = PRESUBMIT.GroupPythonFilesByRoot(input_api, files)
    self.assertEquals(dict(grouped_paths), expected_groups)

  def test_FetchAllFiles(self):
    files = [
      'PRESUBMIT.py',
      'bootstrap/foo.py',
      'infra/__init__.py',
      'infra/bar/__init__.py',
      'infra/bar/baz.py',
      'infra/bar/zoo.html',
      'infra/foo.py',
      'infra/README',
    ]
    input_api = MockInputAPI(files)

    # FIXME: Why are these regexp's instead of globs?
    white_list = [
      '.*\.py',
    ]
    black_list = [
      '.*/__init__\.py',
      'infra/bar'
    ]

    expected_paths = [
      'PRESUBMIT.py',
      'bootstrap/foo.py',
      'infra/foo.py',
    ]

    python_paths = PRESUBMIT.FetchAllFiles(input_api, white_list, black_list)
    # Note that the files are repo-relative (no '/')
    self.assertEquals(python_paths, expected_paths)


  def test_EnvAddingPythonPath(self):
    input_api = MockInputAPI()
    paths = ['badlkfjsdf', 'asdlkfjadf']
    env = PRESUBMIT.EnvAddingPythonPath(input_api, paths)
    for path in paths:
      self.assertIn(path, env['PYTHONPATH'])

  def test_DirtyRootsFromAffectedFiles(self):
    dirty_files = [
      'PRESUBMIT.py',
      'infra/bar/baz.py',
    ]
    roots_to_paths = {
      '': ['PRESUBMIT.py'],
      'bootstrap': ['bootstrap/foo.py'],
      'infra': [
        'infra/__init__.py',
        'infra/bar/__init__.py',
        'infra/bar/baz.py',
        'infra/foo.py',
      ],
    }
    expected_dirty_roots = set(['', 'infra'])
    dirty_roots = PRESUBMIT.DirtyRootsFromAffectedFiles(dirty_files,
        roots_to_paths)
    self.assertEquals(expected_dirty_roots, dirty_roots)


if __name__ == '__main__':
  unittest.main()
