#!/usr/bin/env python

"""Very sloppy Unix-only manual smoke test for cloudtail.

It ensures cloudtail doesn't block stdin (and drops logs instead) and terminates
fast enough, even if stuck retrying HTTP 429 errors.
"""

import contextlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time


SRC_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BINARY = os.path.join(SRC_PATH, 'cmd', 'cloudtail', 'cloudtail')


def build():
  print 'Building %s...' % BINARY
  if os.path.exists(BINARY):
    os.remove(BINARY)  # just to make sure we don't run stale binary by mistake
  subprocess.check_call(['go', 'build', '.'], cwd=os.path.dirname(BINARY))


def cloudtail(*args, **kwargs):
  args = list(args)
  args.extend(['-local-log-level', 'debug', '-debug', '-project-id', 'fake'])
  print 'Running cloudtail %s' % ' '.join(args)
  return subprocess.Popen([BINARY] + args, **kwargs)


def parse_debug_out(out):
  entries = []

  def flush(buf):
    assert buf[0].startswith('To ')
    obj = json.loads('\n'.join(buf[1:]))
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
  buf = []

  def run():
    while True:
      out = stream.read()
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
    entries = parse_debug_out(''.join(out))
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
    entries = parse_debug_out(''.join(out))
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
    entries = parse_debug_out(''.join(out))
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
    entries = parse_debug_out(''.join(out))
    assert len(entries) == i, len(entries)
    assert proc.returncode == 0, proc.returncode


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
