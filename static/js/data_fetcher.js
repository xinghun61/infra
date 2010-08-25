// Copyright (c) 2009 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Helper that fetches the tree status data from a server.
 *
 * The public method it exports is:
 *   DataFetcher.GetTreeStatusEntries(timeRange, callback) method.
 */
var DataFetcher = {};

// -----------------------------------------------------------------------------
// Private implementation
// -----------------------------------------------------------------------------
(function() {

/**
 * Downloads a single url and calls callback(text,error) on completion.
 *
 * @param {string} url
 * @param {function} callback
 */
function Fetch(url, callback) {
  var r = new XMLHttpRequest();
  r.open("GET", url, true);
  r.setRequestHeader("pragma", "no-cache");
  r.setRequestHeader("cache-control", "no-cache");
  r.onreadystatechange = function() {
    if (r.readyState == 4) {
      var error;
      var text = r.responseText;
      if (r.status != 200) {
        error = url + ": " + r.status + ": " + r.statusText;
      } else if (! text) {
        error = url + ": null response";
      }
      callback(text, error);
    }
  }

  r.send(null);
}

/**
 * Trims trailing/leading whitespace from |str|.
 *
 * @param {string} str
 */
function trim(str) {
  return str.replace(/^\s+|\s+$/g, '');
}

/**
 * Parses response (text, error) and appends the parsed entry to |entries|.
 *
 * /allstatus returns entries as "<author>, <date>,<message>\n" lines, with
 * a header line reading "Who,When,Message\n".
 *
 */
function ParseDataResponseAndAppend(entries, text, error) {
  if (error) {
    // If we failed to download the file, error.
    Log("Failed to retrieve the data from server. Error:\n" + error);
    return false;  // failure.
  }

  var lines = text.split("\n");

  // Check that the input is in a format we expect.
  if (lines.length.length < 2 || lines[0] != "Who,When,GeneralStatus,Message") {
    Log("Server returned: " + text);
    return false;
  }

  // Skip the header line.
  for (var i = 1; i < lines.length; ++i) {
    var line = trim(lines[i]);

    if (line.length == 0)
      continue;

    // Comma separated parts (the message part may itself contain commas).
    var parts = /^([^,]*),([^,]*),([^,]*),(.*)$/.exec(line);
    if (!parts) {
      Log("Failed to parse server response line: " + line);
      continue;
    }

    var author = trim(parts[1]);
    var dateStr = trim(parts[2]);
    var general_state = trim(parts[3]);
    var message = trim(parts[4]);

    // The time has a trailing ".XXXXX" component we don't care for.
    // Also append "UTC" so we are left with a string resembling:
    // "2009-10-14 21:59:18 UTC"
    dateStr = dateStr.split(".")[0] + " UTC";

    entries.push(new Entry(DateUtil.ParseUTCDateTimeString(dateStr), author,
                           message, general_state));
  }

  return true;  // success.
}

/**
 * Fetches all of the tree status data relating to |range|.
 * On completion |callback(entries)| is invoked, where |entries| is a list of
 * Entry instances.
 *
 * @param {TimeRange} timeRange
 * @param {function} callback
 */
DataFetcher.GetTreeStatusEntries = function(timeRange, callback) {
  // Convert milliseconds to seconds, since the server is epxecting
  // seconds.
  var startTime = DateUtil.MillisToSeconds(timeRange.startTime);
  var endTime = DateUtil.MillisToSeconds(timeRange.endTime);

  // The peak hours view may need extra time for its day view.
  // Lets go ahead and optimisitically ask for it, just in case...
  startTime += DateUtil.MillisToSeconds(DateUtil.MILLIS_PER_DAY);
  endTime -= DateUtil.MillisToSeconds(DateUtil.MILLIS_PER_DAY);

  var url = "/allstatus?startTime=" + startTime + "&endTime=" + endTime;

  Fetch(url, OnFetchedDataComplete.bind(this, callback));
}

/**
 * Callback for when the data has been fetched.
 *
 * @param {function} callback The user's callback.
 * @param {string} text The contents of the response.
 * @param {string} error Any error message, or undefined on success.
 */
function OnFetchedDataComplete(callback, text, error) {
  var entries = [];
  var ok = ParseDataResponseAndAppend(entries, text, error);
  // TODO(eroman): Fix login situation.
  if (!ok)
    alert("TODO: You probably aren't logged in; try doing that first.");
  callback(entries);
}

})();  // Private implementation.
