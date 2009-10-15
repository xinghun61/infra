// Copyright (c) 2009 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Represents a record in the tree status database.
 *
 * @param {int} timestamp Unix timestamp in milliseconds.
 * @param {string} author
 * @param {string} message
 * @constructor
 */
function Entry(timestamp, author, message) {
  this.timestamp = timestamp;
  this.author = author;
  this.message = message;
}

/**
 * Gets the tree status enumeration for this entry.
 * @return {string} One of the possible tree states.
 *
 * See Entry.TREE_STATES for the enumeration of possible values.
 */
Entry.prototype.GetTreeState = function() {
  // See definition of IsOracle().
  if (this.IsOracle())
    return "unknown";

  var lowercaseMessage = this.message.toLowerCase();

  // Matches common mispelling "tree is close" as well.
  var isClosed = /closed/.test(lowercaseMessage) ||
                 /is close/.test(lowercaseMessage);

  if (isClosed && /maintenance/.test(lowercaseMessage)) {
    return "maintenance";
  }

  if (isClosed)
    return "closed";

  return "open";
}

Entry.TREE_STATES = [
  "open",
  "closed",
  "maintenance", // Tree is closed (for maintenance)
  "unknown"
];

// When building runs for display, we may insert a fake entry to fill the gaps
// remaining in a day. These fake entries will use the magic author of "oracle"
// to indicate that they are not real.
Entry.AUTHOR_ORACLE = "The oracle";

Entry.prototype.IsOracle = function() {
  return this.author == Entry.AUTHOR_ORACLE;
}

/**
 * This class implements a counter for each of the tree status types.
 * Always favor this over a raw dictionary, since it is easier to fix
 * callers when new status types are added.
 */
function StatusTotals() {
  // Init all totals to 0.
  this.totals_ = {};
  for (var i = 0; i < Entry.TREE_STATES.length; ++i) {
    this.totals_[Entry.TREE_STATES[i]] = 0;
  }
}

StatusTotals.prototype.Increment = function(type, value) {
  this.totals_[type] += value;
}

StatusTotals.prototype.GetOpen = function(type) {
  return this.totals_["open"];
}

StatusTotals.prototype.GetClosed = function(type) {
  return this.totals_["closed"] + this.totals_["maintenance"];
}

StatusTotals.prototype.GetClosedForMaintenance = function(type) {
  return this.totals_["maintenance"];
}

StatusTotals.prototype.GetUnknown = function(type) {
  return this.totals_["unknown"];
}

StatusTotals.prototype.GetTotal = function(type) {
  var total = 0;
  for (var key in this.totals_) {
    total += this.totals_[key];
  }
  return total;
}

StatusTotals.prototype.GetTotalKnown = function(type) {
  return this.GetTotal() - this.GetUnknown();
}

/**
 * A "run" shows the time range that an entry was active for.
 *
 * In particular, it describes |entry| as having lasted from for
 * [startTime - duration, startTime).
 *
 * Note that entry.timestamp may be earlier than (startTime - duration) when we
 * are cutting runs at day boundaries.
 *
 * @param {Entry} entry
 * @param {int} startTime Unix timestamp in milliseconds when the entry *ENDS*.
 * @param {int} duration Number of milliseconds the entry is active for,
 * starting from startTime.
 * @constructor
 */
function Run(entry, startTime, duration) {
  this.entry = entry;
  this.startTime = startTime;
  this.duration = duration;
}

/**
 * Returns the end timestamp of the run (inclusive).
 * @return {int}
 */
Run.prototype.GetEndTime = function() {
  return this.startTime - this.duration;
}

/**
 * Builds a list of "runs" that span |timeRange|, pulling data from |entries|.
 *
 * @param {array<Entry>} entries Records sorted from most recent to oldest.
 * @param {TimeRange} timeRange
 * @return {array<Run>}
 */
function MakeRuns(entries, timeRange) {
  var runs = [];

  for (var i = 0; i < entries.length; ++i) {
    var prevEntry = i == 0 ? null : entries[i-1];
    var entry = entries[i];
    var nextEntry = i + 1 == entries.length ? null : entries[i + 1];

    if (entry.timestamp > timeRange.startTime)
      continue;

    var runStartTime;
    var duration;

    if (runs.length == 0) {
      // Connect the startTime to this entry.
      runStartTime = timeRange.startTime;

      if (!prevEntry) {
        // We don't know what the future holds...
        // Extrapolate current status only until the current time.
        var curTime = (new Date()).getTime();
        if (curTime >= timeRange.endTime && curTime < timeRange.startTime) {
          runStartTime = Math.min(curTime, timeRange.startTime);
        }
      }
    } else {
      runStartTime = prevEntry.timestamp;
    }

    var runEndTime = entry.timestamp < timeRange.endTime ?
        timeRange.endTime : entry.timestamp;

    if (runs.length == 0 && runStartTime != timeRange.startTime) {
      var unknownEntry = new Entry(runStartTime, Entry.AUTHOR_ORACLE,
                                   "Your future is uncertain...");
      // Add an unknown filler.
      runs.push(new Run(unknownEntry, timeRange.startTime,
                        timeRange.startTime - runStartTime));
    }

    runs.push(new Run(entry, runStartTime, runStartTime - runEndTime));

    if (runEndTime == timeRange.endTime) {
      break;
    }
  }

  // The runs are supposed to span the entire time range. If any data was
  // missing add a filler run.
  var lastEndTime = runs.length == 0 ?
      timeRange.startTime : runs[runs.length - 1].GetEndTime();
  if (lastEndTime != timeRange.endTime) {
    var unknownEntry = new Entry(timeRange.endTime, Entry.AUTHOR_ORACLE,
                                 "Missing data!");
    runs.push(new Run(unknownEntry, lastEndTime,
                      lastEndTime - timeRange.endTime));
  }

  return runs;
}
