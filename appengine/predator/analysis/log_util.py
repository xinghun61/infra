# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility functions to log information to datastore and stackdriver."""

from analysis.type_enums import LogLevel
import logging


def Log(log, name, message, level, stackdriver_logging=True):
  """Log message to ``log`` entry."""
  if stackdriver_logging:
    getattr(logging, level)(message)

  if log:
    log.Log(name, message, level)


def LogInfo(log, name, message, stackdriver_logging=True):
  """Log info level message to ``log`` entry."""
  Log(log, name, message, LogLevel.INFO,
      stackdriver_logging=stackdriver_logging)


def LogWarning(log, name, message, stackdriver_logging=True):
  """Log warning level message to ``log`` entry."""
  Log(log, name, message, LogLevel.WARNING,
      stackdriver_logging=stackdriver_logging)


def LogError(log, name, message, stackdriver_logging=True):
  """Log error level message to ``log`` entry."""
  Log(log, name, message, LogLevel.ERROR,
      stackdriver_logging=stackdriver_logging)
