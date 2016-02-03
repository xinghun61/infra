# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility functions for handling flakes."""

import datetime


def is_last_hour(date):
  return (datetime.datetime.utcnow() - date) < datetime.timedelta(hours=1)


def is_last_day(date):
  return (datetime.datetime.utcnow() - date) < datetime.timedelta(days=1)


def is_last_week(date):
  return (datetime.datetime.utcnow() - date) < datetime.timedelta(weeks=1)


def is_last_month(date):
  return (datetime.datetime.utcnow() - date) < datetime.timedelta(days=31)


def add_occurrence_time_to_flake(flake, occurrence_time):
  if occurrence_time > flake.last_time_seen:
    flake.last_time_seen = occurrence_time
  if is_last_hour(occurrence_time):
    flake.count_hour += 1
    flake.last_hour = True
  if is_last_day(occurrence_time):
    flake.count_day += 1
    flake.last_day = True
  if is_last_week(occurrence_time):
    flake.count_week += 1
    flake.last_week = True
  if is_last_month(occurrence_time):
    flake.count_month += 1
    flake.last_month = True
  flake.count_all += 1
