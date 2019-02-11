#!/usr/bin/env vpython

import subprocess

print "Hello"

nb_child = 3
procs = [
  subprocess.Popen(["vpython", "child%d/child.py" % ((nb_child%2)+1), str(i)])
  for i in xrange(nb_child*5)
]
for p in procs:
  p.wait()
