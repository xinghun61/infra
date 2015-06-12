// Copyright (c) 2009 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Factory function to create a View for statistics.
 *
 * The statistics view shows some aggregate totals like how many total hours the
 * tree remained closed in the time range.
 */
var CreateStatsView;

// -----------------------------------------------------------------------------
// Private implementation
// -----------------------------------------------------------------------------

(function() {

CreateStatsView = function(timeRange, entries) {
  return new StatsView(timeRange, entries);
};

function StatsView(timeRange, entries) {
  DrawStatsView(timeRange, entries);
}

StatsView.prototype.Show = function(visible) {
  gViewerApp.ShowViewContentAndTabArea('stats', visible);
};

/**
 * Helper that does |map[key] += increment| (lazy-initializing to 0).
 */
function IncrementProperty(map, key, increment) {
  var prevValue = map[key];
  if (prevValue === undefined)
    prevValue = 0;
  map[key] = prevValue + increment;
}

/**
 * Transforms a map from values --> counts to a list of
 * (value, count). This list is sorted by count.
 *
 * @param {Object} map
 * @param {Object} topCount How many of the top items to keep.
 * @return {array<Object>}
 */
function GetTopItems(map, topCount) {
  var topItems = [];

  for (var key in map) {
    topItems.push({key: key, value: map[key]});
  }

  var sortFunc = function(a, b) {
    return b.value - a.value;
  };

  topItems.sort(sortFunc);

  if (topItems.length > topCount) {
    topItems.length = topCount;
  }

  return topItems;
}

/**
 * These are words we don't want to count as being "top" words.
 * They are fairly common, but not particularly useful.
 */
var SKIP_WORDS = {
  "": true,
  "a": true,
  "and": true,
  "at": true,
  "be": true,
  "chromium": true,
  "closed": true,
  "com": true,
  "for": true,
  "from": true,
  "go": true,
  "google": true,
  "green": true,
  "if": true,
  "in": true,
  "is": true,
  "it": true,
  "on": true,
  "open": true,
  "org": true,
  "tests": true,
  "the": true,
  "throttled": true,
  "to": true,
  "too": true,
  "tree": true,
  "will": true
};

/**
 * Splits |str| into an array of words. Excludes any of the words in
 * |SKIP_WORDS|.
 *
 * @param {string} str
 * @return {array<string>}
 */
function GetKeyWords(str) {
  var rawWords = str.split(/\W+/);

  var words = [];

  for (var i = 0; i < rawWords.length; ++i) {
    var word = rawWords[i].toLowerCase();
    if (!SKIP_WORDS[word]) {
      words.push(word);
    }
  }

  return words;
}

/**
 * Calculates a bunch of statistics for |runs| and returns it in
 * an object.
 *
 * @param {array<Run>} runs
 * @param {int} topN How may of the top words/authors to track.
 * @return {Object}
 */
function CalculateStatistics(runs, topN) {
  var authors = {};
  var words = {};

  // Total times (in seconds) for all the statuses.
  var statusTotalsSeconds = new StatusTotals();

  // First we iterate through all the entries, and build a map from
  // word --> count.
  for (var i = 0; i < runs.length; ++i) {
    var run = runs[i];

    // Don't count our bogus entry, as it will mess up the top words/authors.
    if (run.entry.IsOracle())
      continue;

    IncrementProperty(authors, run.entry.author.toLowerCase(), 1);
    
    var durationSeconds = DateUtil.MillisToSeconds(run.duration);
    var state = run.entry.GetTreeState();
    statusTotalsSeconds.Increment(state, durationSeconds);

    // Split the message into keywords, and tally each of them up.
    var keywords = GetKeyWords(run.entry.message);
    for (var j = 0; j < keywords.length; ++j) {
      IncrementProperty(words, keywords[j], 1);
    }
  }

  return {
    topAuthors: GetTopItems(authors, topN),
    topWords: GetTopItems(words, topN),
    statusTotalsSeconds: statusTotalsSeconds
  };
}

function DrawTimeTotal(parent, title, x, total) {
  var text = title + ": " +
        FormatSeconds(x) + " of " + FormatSeconds(total) + " (" +
        ((x / total) * 100).toFixed(2) + "%)";
  DomUtil.AddText(parent, text);
  DomUtil.AddNode(parent, "br");
}

function DrawStatsView(timeRange, allEntries) {
  // Calculate the statistics we care about.
  var topN = 10;
  var stats = CalculateStatistics(MakeRuns(allEntries, timeRange), topN);

  var timeClosedDiv = document.getElementById("timeClosed");
  var topAuthorsDiv = document.getElementById("topAuthors");
  var topWordsDiv = document.getElementById("topWords");

  // Clear any existing gank from the HTML.
  timeClosedDiv.innerHTML = "";
  topAuthors.innerHTML = "";
  topWords.innerHTML = "";

  // Time open.
  var timeOpen = stats.statusTotalsSeconds.GetOpen();

  // Time closed due to maintenance.
  var timeMaintenance = stats.statusTotalsSeconds.GetClosedForMaintenance();

  // Time throttled.
  var timeThrottled = stats.statusTotalsSeconds.GetThrottled();

  // Total time.
  var total = stats.statusTotalsSeconds.GetTotalKnown();

  // Draw time totals.
  DrawTimeTotal(timeClosedDiv, "Total time open", timeOpen, total);

  DrawTimeTotal(timeClosedDiv, "Total time open (excluding maintenance)",
                timeOpen + timeMaintenance, total - timeMaintenance);

  DrawTimeTotal(timeClosedDiv, "Total time closed for maintenance",
                timeMaintenance, total);

  DrawTimeTotal(timeClosedDiv, "Total time throttled",
                timeThrottled, total);

  // Draw the top authors/words.
  DrawTopList(topAuthorsDiv, stats.topAuthors);
  DrawTopList(topWordsDiv, stats.topWords);
}

/**
 * Converts |t| which is a duration in seconds, into a human readable string.
 *
 * @param {int} t
 * @return {string}
 */
function FormatSeconds(t) {
  var minutes = t / 60;
  
  if (minutes > 60) {
    var hours = minutes / 60;
    var precision = 1;
    if (hours > 50)
      precision = 0;
    return (hours).toFixed(precision) + " hours";
  }

  return minutes.toFixed(0) + " minutes";
}

/**
 * Draws a UL or OL to |parent|, populating it with |items|.
 * TODO(eroman): move this to DomUtil.
 *
 * @param {DOMNode} parent
 * @param {array<string>} items
 * @param {string} name Either "ul" or "ol".
 */
function DrawList(parent, items, name) {
  var ul = DomUtil.AddNode(parent, name);

  for (var i = 0; i < items.length; ++i) {
    var li = DomUtil.AddNode(ul, "li");
    DomUtil.AddText(li, items[i]);
  }
}

function DrawTopList(parent, topList) {
  var items = [];
  for (var i = 0; i < topList.length; ++i) {
    var str = "[" + topList[i].value + "] " + topList[i].key;
    items.push(str);
  }
  DrawList(parent, items, "ol");
}

})();  // Private implementation.
