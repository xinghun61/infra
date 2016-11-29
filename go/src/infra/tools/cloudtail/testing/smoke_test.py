#!/usr/bin/env python

"""Very sloppy Unix-only manual smoke test for cloudtail.

It ensures cloudtail doesn't block stdin (and drops logs instead) and terminates
fast enough, even if stuck retrying HTTP 429 errors.
"""

import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time


SRC_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BINARY = os.path.join(SRC_PATH, 'cmd', 'cloudtail', 'cloudtail')


class Buffer(object):
  def __init__(self):
    self.lock = threading.Lock()
    self.buf = []

  def append(self, itm):
    with self.lock:
      self.buf.append(itm)

  def collect(self):
    with self.lock:
      out, self.buf = self.buf, []
      return out

  def wait(self):
    while True:
      out = self.collect()
      if out:
        return out
      time.sleep(0.1)


class LogFile(object):
  def __init__(self, path):
    self.path = path
    self.f = open(self.path, 'wt')

  def close(self):
    self.f.close()

  def write(self, line):
    self.f.write(line + '\n')
    self.f.flush()
    os.fsync(self.f.fileno())

  def rotate(self, suffix):
    self.f.close()
    os.rename(self.path, self.path+suffix)
    self.f = open(self.path, 'wt')


def build():
  print 'Building %s...' % BINARY
  if os.path.exists(BINARY):
    os.remove(BINARY)  # just to make sure we don't run stale binary by mistake
  subprocess.check_call(['go', 'build', '.'], cwd=os.path.dirname(BINARY))


def cloudtail(*args, **kwargs):
  fast_flush = kwargs.pop('fast_flush', False)
  args = list(args)
  args.extend(['-local-log-level', 'debug', '-project-id', 'fake', '-debug'])
  if fast_flush:
    args.extend(['-buffering-time', '1ms'])
  print 'Running cloudtail %s' % ' '.join(args)
  return subprocess.Popen([BINARY] + args, bufsize=1, **kwargs)


def parse_debug_out(out):
  entries = []

  def flush(buf):
    obj = json.loads(''.join(buf))
    entries.extend(e['textPayload'] for e in obj['entries'])

  buf = None
  for line in out.split('\n'):
    if not line:
      continue
    is_sep = line == '----------'
    if buf is not None:
      if is_sep:
        flush(buf)
        buf = None
      else:
        buf.append(line)
    elif is_sep:
      buf = []
    else:
      print 'Unexpected debug output line:\n%s' % line

  return entries


@contextlib.contextmanager
def timeout(t):
  def handler(*_):
    print 'TIMEOUT! Running longer than %d sec' % t
    sys.stdout.flush()
    os._exit(1)
  signal.signal(signal.SIGALRM, handler)
  signal.alarm(t)
  yield
  signal.alarm(0)


def reader_thread(stream):
  buf = Buffer()

  def run():
    while True:
      out = stream.readline()
      if not out:
        break
      buf.append(out)

  t = threading.Thread(target=run)
  t.daemon = True
  t.start()

  return t, buf


def producer_loop(stream, interval=0.005, duration=4):
  i = 0
  deadline = time.time() + duration
  while time.time() < deadline:
    if i % 100 == 0:
      print '%.1f sec yet to run' % (deadline - time.time(),)
    with timeout(1):
      stream.write('line %d\n' % i)
      stream.flush()
    i+=1
    time.sleep(interval)
  print '%d entries sent' % i
  return i


def test_send(assert_all_sent=True):
  with timeout(10):
    proc = cloudtail('send', '-text', 'hi!', stdout=subprocess.PIPE)
    entries = parse_debug_out(proc.communicate()[0])
    if assert_all_sent:
      assert entries == ['hi!']
      assert proc.returncode == 0, proc.returncode


def test_pipe_gazillion_lines():
  data = '\n'.join('line %d' % i for i in xrange(0, 2000000))
  print 'Piping %d Mb...' % (len(data)/1024/1024,)
  with timeout(15):
    proc = cloudtail('pipe', stdout=subprocess.PIPE, stdin=subprocess.PIPE)
    proc.communicate(data)
    # It should drop stuff.
    assert proc.returncode != 0, proc.returncode


def test_pipe_send_one_line_and_wait(assert_all_sent=True):
  proc = cloudtail('pipe', stdout=subprocess.PIPE, stdin=subprocess.PIPE)
  reader, out = reader_thread(proc.stdout)

  proc.stdin.write('hi!\n')
  proc.stdin.flush()

  # The flush should happen after ~5 sec.
  time.sleep(7)

  # Brutally kill to deny graceful flush on shutdown.
  print 'Killing cloudtail'
  os.kill(proc.pid, signal.SIGKILL)
  with timeout(10):
    reader.join(timeout=10)
    proc.wait()
  proc.stdin.close()
  proc.stdout.close()

  # Ensure the line was sent.
  if assert_all_sent:
    entries = parse_debug_out(''.join(out.collect()))
    assert entries == ['hi!']


def test_pipe_big_buf_until_eof(assert_all_sent=True):
  lines_to_send = ['line %d' % i for i in xrange(0, 100000)]

  with timeout(10):
    proc = cloudtail('pipe', stdout=subprocess.PIPE, stdin=subprocess.PIPE)
    out = proc.communicate('\n'.join(lines_to_send))[0]

  if assert_all_sent:
    entries = parse_debug_out(out)
    assert lines_to_send == entries, len(entries)
    assert proc.returncode == 0, proc.returncode


def test_pipe_steady_rate_until_eof(assert_all_sent=True):
  proc = cloudtail('pipe', stdout=subprocess.PIPE, stdin=subprocess.PIPE)

  # Need to read stdout asynchronously to not block the cloudtail writing to it.
  reader, out = reader_thread(proc.stdout)

  # Produce stuff at a constant rate then EOF.
  i = producer_loop(proc.stdin, duration=10)
  proc.stdin.close()

  print 'Waiting for cloudtail to terminate'
  with timeout(10):
    reader.join(timeout=10)
    proc.wait()
  proc.stdout.close()

  # Make sure all lines were sent.
  if assert_all_sent:
    entries = parse_debug_out(''.join(out.collect()))
    assert len(entries) == i, len(entries)
    assert proc.returncode == 0, proc.returncode


def test_pipe_steady_rate_and_sigint(assert_all_sent=True):
  proc = cloudtail('pipe', stdout=subprocess.PIPE, stdin=subprocess.PIPE)

  # Need to read stdout asynchronously to not block the cloudtail writing to it.
  reader, out = reader_thread(proc.stdout)

  # Produce stuff at a constant rate then SIGINT of cloudtail.
  i = producer_loop(proc.stdin, duration=10)
  os.kill(proc.pid, signal.SIGINT)

  # Cloudtail should flush all pending data it currently has and exit ASAP.
  print 'Waiting for cloudtail to terminate'
  with timeout(10):
    reader.join(timeout=10)
    proc.wait()

  proc.stdin.close()
  proc.stdout.close()

  # Make sure all lines were sent.
  if assert_all_sent:
    entries = parse_debug_out(''.join(out.collect()))
    assert len(entries) == i, len(entries)
    assert proc.returncode == 0, proc.returncode


def test_tail_steady_rate(assert_all_sent=True):
  with tempfile.NamedTemporaryFile() as f:
    proc = cloudtail('tail', '-path', f.name, stdout=subprocess.PIPE)

    # Need to read stdout asynchronously to not block the cloudtail writing.
    reader, out = reader_thread(proc.stdout)

    print 'Waiting for tailer to initialize itself'
    time.sleep(2)

    # Produce stuff at a constant rate then SIGINT of cloudtail.
    i = producer_loop(f, duration=10)

    print 'Waiting for tailer to catch up'
    time.sleep(5)
    os.kill(proc.pid, signal.SIGINT)

    # Cloudtail should flush all pending data it currently has and exit ASAP.
    print 'Waiting for cloudtail to terminate'
    with timeout(10):
      reader.join(timeout=10)
      proc.wait()
    proc.stdout.close()

  if assert_all_sent:
    entries = parse_debug_out(''.join(out.collect()))
    assert len(entries) == i, len(entries)
    assert proc.returncode == 0, proc.returncode


def test_tail_rotation():
  try:
    base_dir = tempfile.mkdtemp('cloudtail_test')
    log_file = LogFile(os.path.join(base_dir, 'log'))

    proc = cloudtail(
        'tail', '-path', log_file.path, stdout=subprocess.PIPE, fast_flush=True)
    reader, out = reader_thread(proc.stdout)

    # Give it some time to start watching the file.
    print 'Waiting for tailer to initialize itself'
    time.sleep(2)

    # To emulate a shortage of inotify watches:
    # sudo sysctl fs.inotify.max_user_watches=100
    for i in xrange(0, 200):
      print 'Attempt %d' % i
      with timeout(10):
        log_file.write('Hello!')
        out.wait()  # make sure cloudtail consumed the log line
        log_file.rotate(str(i))

    print 'Stopping cloudtail'
    os.kill(proc.pid, signal.SIGINT)
    with timeout(10):
      reader.join(timeout=10)
      proc.wait()
    proc.stdout.close()

  finally:
    log_file.close()
    shutil.rmtree(base_dir)


def main():
  if sys.platform == 'win32':
    print 'Not supported on Win32'
    return 1

  build()

  print '-'*80
  print 'Emulating successful writes'
  print '-'*80

  test_send()
  test_pipe_send_one_line_and_wait()
  test_pipe_big_buf_until_eof()
  test_pipe_gazillion_lines()
  test_pipe_steady_rate_until_eof()
  test_pipe_steady_rate_and_sigint()
  test_tail_steady_rate()
  test_tail_rotation()

  print
  print '-'*80
  print 'Emulating HTTP 429. Everything should terminate fast enough.'
  print '-'*80
  print
  os.environ['CLOUDTAIL_DEBUG_EMULATE_429'] = '1'

  test_send(assert_all_sent=False)
  test_pipe_send_one_line_and_wait(assert_all_sent=False)
  test_pipe_big_buf_until_eof(assert_all_sent=False)
  test_pipe_gazillion_lines()
  test_pipe_steady_rate_until_eof(assert_all_sent=False)
  test_pipe_steady_rate_and_sigint(assert_all_sent=False)
  test_tail_steady_rate(assert_all_sent=False)

  print
  print '-'*80
  print 'SUCCESS'
  print '-'*80


if __name__ == '__main__':
  sys.exit(main())
