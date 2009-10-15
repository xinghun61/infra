// Copyright (c) 2009 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Represents a span of time from [endTime, startTime).
 *
 * (Note that startTime is more recent than endTime).
 *
 * @param {int} startTime Unix timestamp in milliseconds.
 * @param {int} endTime Unix timestamp in milliseconds.
 * @constructor
 */
function TimeRange(startTime, endTime) {
  this.startTime = startTime;
  this.endTime = endTime;
}

/**
 * Helper class with time/date functions functions.
 */
var DateUtil = {};

/**
 * The number of seconds in an hour.
 */
DateUtil.SECONDS_PER_HOUR = 60 * 60;

/**
 * The number of milliseconds in an hour.
 */
DateUtil.MILLIS_PER_HOUR = DateUtil.SECONDS_PER_HOUR * 1000;

/**
 * The number of milliseconds in a day.
 */
DateUtil.MILLIS_PER_DAY = DateUtil.MILLIS_PER_HOUR * 24;

/**
 * Parses a date resembling "2009-10-23" into a unix timestamp (milliseconds).
 * Assumes the timezone for the date is UTC. Sets the time component to
 * midnight.
 *
 * @param {string} dateStr
 * @return {int} Unix timestamp in milliseconds.
 */
DateUtil.ParseUTCDateString = function(dateStr) {
  var parts = dateStr.split("-");
  return Date.UTC(parseInt(parts[0], 10), // year
                  parseInt(parts[1], 10) - 1, // month
                  parseInt(parts[2], 10), // day
                  0, 0, 0);
}

/**
 * Parses a date resembling "2009-10-23" into a Date object.
 * Assumes the local timezeone for the date. Sets the time component to
 * midnight (of local timezone).
 *
 * @param {string} dateStr
 * @return {Date} Valid date object, or null if failed.
 */
DateUtil.ParseStringToLocalDate = function(dateStr) {
  // We support both "2009/10/23" and "2009-10-23".
  // Normalize to a format using "-".
  dateStr = dateStr.replace(/-/g, "/");

  var parts = dateStr.split("/");

  if (parts.length != 3)
    return null;  // Failed to parse.

  var d = new Date(parseInt(parts[0], 10), // year
                   parseInt(parts[1], 10) - 1, // month
                   parseInt(parts[2], 10), // day
                   0, 0, 0);
  return d;
}

/**
 * Parses a date/time string resembling "2009-10-06 22:53:32 UTC" to a unix
 * timestamp.
 *
 * @param {string} dateStr
 * @return {int} Unix timestamp in milliseconds.
 */
DateUtil.ParseUTCDateTimeString = function(dateStr) {
  var parts = dateStr.split(" ");

  if (parts.length != 3 || parts[2] != "UTC") {
    Log("Invalid formatted dateStr: " + dateStr);
    return 0;
  }

  var d = new Date();
  d.setTime(DateUtil.ParseUTCDateString(parts[0]));

  var timeParts = parts[1].split(":");

  if (timeParts.length < 2) {
    Log("Invalid formatted dateStr: " + dateStr);
    return 0;
  }

  d.setUTCHours(parseInt(timeParts[0], 10));
  d.setUTCMinutes(parseInt(timeParts[1], 10));
  if (timeParts.length > 2)
    d.setUTCSeconds(parseInt(timeParts[2], 10));
  return d.getTime();
}

/**
 * Formats |x| in decimal such that it occupies |count| characters.
 */
function PadWithZero(x, count) {
  var s = "" + x;
  while (s.length < count)
    s = "0" + s;
  return s;
}

/**
 * Returns a time range for the day that encloses |t| (in the local
 * timezone. Anchored at midnight.
 *
 * @param {int} t Unix timestamp in milliseconds.
 * @return {TimeRange}
 */
DateUtil.GetLocalDayRange = function(t) {
  var d = new Date();
  d.setTime(t);

  // Midnight
  d.setHours(0);
  d.setMinutes(0);
  d.setSeconds(0);
  d.setMilliseconds(0);

  var endTime = d.getTime();
  var startTime = endTime + DateUtil.MILLIS_PER_DAY;

  return new TimeRange(startTime, endTime);
}

/**
 * Returns a time range for the day that encloses |t| in UTC
 * Anchored at midnight.
 *
 * @param {int} t Unix timestamp in milliseconds.
 * @return {TimeRange}
 */
DateUtil.GetUTCDayRange = function(t) {
  var d = new Date();
  d.setTime(t);

  // Midnight
  d.setUTCHours(0);
  d.setUTCMinutes(0);
  d.setUTCSeconds(0);
  d.setMilliseconds(0);

  var endTime = d.getTime();
  var startTime = endTime + DateUtil.MILLIS_PER_DAY;

  return new TimeRange(startTime, endTime);
}

/**
 * Returns a list of all of the days contained by |timeRange|,
 * using the current timezone.
 *
 * @param {TimeRange} timeRange.
 * @return {array<TimeRange>}
 */
DateUtil.GetLocalDaysInRange = function(timeRange) {
  var days = [];

  var t = timeRange.startTime;
  t -= DateUtil.MILLIS_PER_DAY;

  while (t >= timeRange.endTime) {
    var day = DateUtil.GetLocalDayRange(t);
    days.push(day);
    t -= DateUtil.MILLIS_PER_DAY;
  }

  return days;
}

/**
 * Returns a list of all of the days contained by |timeRange|,
 * as UTC days.
 *
 * @param {TimeRange} timeRange.
 * @return {array<TimeRange>}
 */
DateUtil.GetUTCDaysInRange = function(timeRange) {
  var days = [];

  var t = timeRange.startTime;
  t -= DateUtil.MILLIS_PER_DAY;

  while (t >= timeRange.endTime) {
    var day = DateUtil.GetUTCDayRange(t);
    days.push(day);
    t -= DateUtil.MILLIS_PER_DAY;
  }

  return days;
}

/**
 * Formats |t| as something human readable in the user's current locale.
 *
 * @param {int} t Unix timestamp in milliseconds.
 * @return {string}
 */
DateUtil.FormatAsLocalDate = function(t) {
  // Format the date into something readable.
  var d = new Date();
  d.setTime(t);
  return d.toLocaleString();
}

/**
 * Converts milliseconds to seconds (rounding down).
 *
 * @param {int} millis
 * @return {int}
 */
DateUtil.MillisToSeconds = function(millis) {
  return parseInt((millis / 1000).toFixed(0));
}

