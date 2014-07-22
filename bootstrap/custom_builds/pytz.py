import os
import subprocess

def Build(source_path, wheelhouse_path):
  subprocess.check_call(
      ['make', 'CFLAGS=-DSTD_INSPIRED', '.stamp-tzinfo'], cwd=source_path)

  path = os.path.join(source_path, 'src')
  subprocess.check_call(
      ['python', 'setup.py', 'bdist_wheel', '--dist-dir', wheelhouse_path],
      cwd=path)
