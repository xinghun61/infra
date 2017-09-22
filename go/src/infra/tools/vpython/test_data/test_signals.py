# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import signal
import sys
import threading
import time

# Wait for interrupt signal.
signalled = False
def signal_handler(_sig, _frame):
  global signalled
  print 'Received SIGINT!'
  signal.signal(signal.SIGINT, signal.SIG_DFL)
  signalled = True
signal.signal(signal.SIGINT, signal_handler)

# sys.argv[1] is the path to the file to delete once we've started.
os.remove(sys.argv[1])

# Loop indefinitely. Our parent process is responsible for killing us.
print 'Waiting for signal...'
while not signalled:
  time.sleep(.1)
print 'Exiting after confirming signal.'
