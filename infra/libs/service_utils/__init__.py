import sys

if sys.platform == 'win32':  # pragma: no cover
  from . import _daemon_win32 as daemon
else:
  from . import _daemon_unix as daemon
