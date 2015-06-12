// Copyright (c) 2009 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Factory function to create a View for "fragmentation".
 *
 * This display of the data shows tree closure/open events as red/green blocks.
 */
var CreateFragmentationView;

// -----------------------------------------------------------------------------
// Private implementation
// -----------------------------------------------------------------------------

(function() {

CreateFragmentationView = function(timeRange, entries) {
  return new FragmentationView(timeRange, entries);
};

function FragmentationView(timeRange, entries) {
  Draw(entries, timeRange);
}

FragmentationView.prototype.Show = function(visible) {
  gViewerApp.ShowViewContentAndTabArea('fragmentation', visible);
};

/**
 * Draws the fragmentation chart for all days in |timeRange|.
 * @param {array<Entry>} entries
 * @param {TimeRange} timeRange
 */
function Draw(entries, timeRange) {
  // Figure out what days we touch.
  var days = DateUtil.GetLocalDaysInRange(timeRange);

  var tbody = document.getElementById("tbody");
  // Clear anything already present in the output table.
  tbody.innerHTML = "";

  // Draw the rows for each day worth of data.
  for (var i = 0; i < days.length; ++i) {
    var day = days[i];
    DrawDay(tbody, entries, day);
  }
}

/**
 * Draws a specific day's row in the fragmentation chart.
 * @param {DOMNode} tbody
 * @param {array<Entry>} entries
 * @param {TimeRange} day
 */
function DrawDay(tbody, entries, day) {
  var tr = DomUtil.AddNode(tbody, "tr");

  var tdForDayName = DomUtil.AddNode(tr, "td");
  DrawDayNameColumn(day, tdForDayName);

  var tableTd = DomUtil.AddNode(tr, "td");

  tableTd.width = "100%";

  // Extract the data from |entries| that apply to |day|, and break it
  // into (start,duration) runs.
  var runs = MakeRuns(entries, day);

  DrawRunsTable(tableTd, runs);
}

/**
 * Draws a specific day's name column in the fragmentation chart.
 * @param {TimeRange} day
 * @param {DOMNode} td The column to print name into.
 */
function DrawDayNameColumn(day, td) {
  var d = new Date();
  d.setTime(day.endTime);

  // Display the day as for example "2009/8/38".
  var dateText =
      d.getFullYear() + "/" +
      PadWithZero(d.getMonth() + 1, 2) + "/" +
      PadWithZero(d.getDate(), 2);

  // Color saturday and sunday differently.
  if (d.getDay() === 0) {
    td.className = "sundayName";
  } else if (d.getDay() == 6) {
    td.className = "saturdayName";
  }

  td.innerHTML = dateText;
}

/**
 * Draws a fragmentation table for |runs|.
 *
 * @param {DOMNode} parent Container to put table into.
 * @param {array<Run>} runs
 */
function DrawRunsTable(parent, runs) {
  var table = DomUtil.AddNode(parent, "table");
  table.cellSpacing = 0;
  table.cellPadding = 0;
  table.width = "100%";

  var tr = DomUtil.AddNode(table, "tr");

  // If we have any entires that lasted less than 1 minute, pretend like
  // they were a minute in length (otherwise they will be too tiny to click on.
  var MIN_DURATION = 60000;

  // Sum up how much total time the runs span.
  var totalDuration = 0;
  for (var i = 0; i < runs.length; ++i) {
    totalDuration += Math.max(MIN_DURATION, runs[i].duration);
  }

  for (var j = 0; j < runs.length; ++j) {
    var run = runs[j];
    var duration = Math.max(MIN_DURATION, run.duration);
    var width = duration / totalDuration;
    AddRunColumn(tr, run, width);
  }
}

/**
 * Inserts a column into |tr| for |run|, which occupies |widthFraction|
 * percentage of space in the row.
 *
 * @param {DOMNode} tr
 * @param {Run} run
 * @param {number} widthFraction
 */
function AddRunColumn(tr, run, widthFraction) {
  var td = DomUtil.AddNode(tr, "td");
  td.className = run.entry.GetTreeState();

  td.width = (100 * widthFraction).toFixed(4) + "%";
  td.innerHTML = "&nbsp;";

  // When users click on the column, display details on the entry.
  td.onclick = function() {
    var msg = "[duration = " + (run.duration / (60 * 1000)).toFixed(0) +
              " minutes]\n\n" +
              DateUtil.FormatAsLocalDate(run.entry.timestamp) + "\n\n" +
              run.entry.author + ":\n\n" +
              run.entry.message;
    alert(msg);
  };
}

})();  // Private implementation.
