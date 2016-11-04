#!/usr/bin/env python

"""Runs cloudtail tests in a loop, in parallel, until first error or Ctrl+C.

Can be used to reproduce flaky errors.
"""

import os
import subprocess
import sys
import threading
import time


THIS_DIR = os.path.dirname(os.path.abspath(__file__))


log_lock = threading.Lock()


def log(idx, i, out):
  with log_lock:
    sys.stdout.write('%d (%d): %s' % (idx, i, out))


def run_loop(binary, idx):
  i = 0
  while True:
    i += 1
    p = subprocess.Popen([
        binary,
        '-convey-silent',
        '-test.timeout=10s',
        '-test.run=TestPushBuffer',
        '-test.cpu=4',
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = p.communicate()
    log(idx, i, out)
    if p.returncode != 0:
      os._exit(1)


def compile_test():
  binary = os.path.join(THIS_DIR, 'cloudtail_test')
  subprocess.check_call([
    'go', 'test', 'infra/tools/cloudtail', '-c', '-o', binary,
  ])
  return binary


def main():
  binary = compile_test()
  for i in range(0, 30):
    t = threading.Thread(target=run_loop, args=(binary, i))
    t.daemon = True
    t.start()
  while True:
    time.sleep(1)


if __name__ == '__main__':
  main()
