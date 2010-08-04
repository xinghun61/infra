// Copyright (c) 2009 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Factory function to create a View for "peak hours".
 *
 * This display of the data shows tree closure/open totals during peak hours in
 * various time zones.
 */
var CreatePeakHoursView;

// -----------------------------------------------------------------------------
// Private implementation
// -----------------------------------------------------------------------------

(function() {

CreatePeakHoursView = function(timeRange, entries) {
  return new PeakHoursView(timeRange, entries);
}

function PeakHoursView(timeRange, entries) {
  Draw(entries, timeRange);
}

PeakHoursView.prototype.Show = function(visible) {
 gViewerApp.ShowViewContentAndTabArea("peak", visible);
}

/**
 * Draws the peak hours chart for all days in |timeRange|.
 * @param {array<Entry>} entries
 * @param {TimeRange} timeRange
 */
function Draw(entries, timeRange) {
  var utcOffsetsMillis = {
    // Please keep this ordered by UTC offset.
    // If you extend this list, you need to adjust column widths in 
    // AddPeakColumn() and on the status_viewer.html page.
    MTV: -7 * DateUtil.MILLIS_PER_HOUR,  // UTC-7 -- Mountain View
    NYC: -4 * DateUtil.MILLIS_PER_HOUR,  // UTC-4 -- New York
    CET: 1 * DateUtil.MILLIS_PER_HOUR,   // UTC+1 -- Denmark
    TOK: 9 * DateUtil.MILLIS_PER_HOUR    // UTC+9 -- Tokyo
  };
  var graphCSV = [];

  // Find which is the minimum and maximum.
  var minUTCOffsetMillis = utcOffsetsMillis.MTV;
  var maxUTCOffsetMillis = utcOffsetsMillis.MTV;

  for (var timezone in utcOffsetsMillis) {
    var offset = utcOffsetsMillis[timezone];
    minUTCOffsetMillis = Math.min(minUTCOffsetMillis, offset);
    maxUTCOffsetMillis = Math.max(maxUTCOffsetMillis, offset);
  }
  
  // Set the graph csv header: "Date,MTV,NYC,CET,TOK\n".
  graphCSV.push("Date");
  for (var timezone in utcOffsetsMillis) {
    graphCSV.push(",");
    graphCSV.push(timezone);
  }
  graphCSV.push("\n");

  // Figure out what days we touch.
  // 
  // Note that we have to extend the time range by the max and
  // minimum offsets, since those timezones may be on the next/previous
  // day!
  var days = DateUtil.GetUTCDaysInRange(
      new TimeRange(timeRange.startTime + maxUTCOffsetMillis,
                    timeRange.endTime + minUTCOffsetMillis));

  var tbody = document.getElementById("peak_tbody");
  // Clear anything already present in the output table.
  tbody.innerHTML = "";

  // Draw the rows for each day worth of data.
  for (var i = 0; i < days.length; ++i) {
    var day = days[i];
    DrawDay(tbody, entries, day, utcOffsetsMillis, graphCSV);
  }

  // Draw a graph with the csv data across all dates.
  // Dygraph docs at http://danvk.org/dygraphs/
  var peakGraph = 
      new Dygraph(document.getElementById("peak_dygraph"),
                  graphCSV.join(""),
                  {
                    rollPeriod: 7,
                    showRoller: true,
                    axisLabelFontSize: 11,
                    includeZero: true,
                    colors: ["red", "orange", "blue", "LightSkyBlue"],
                    strokeWidth: 3,
                    labelsDiv: document.getElementById("peak_dygraph_legend"),
                    labelsSeparateLines: true,
                  });
}

/**
 * Draws a specific day's row in the peak hours chart.
 * @parm {DOMNode} tbody
 * @param {array<Entry>} entries
 * @param {TimeRange} day
 * @param {dict} utcOffsetsMillis
 * @param {array} graphCSV
 */
function DrawDay(tbody, entries, utcDay, utcOffsetsMillis, graphCSV) {
  var tr = DomUtil.AddNode(tbody, "tr");


  var tdForDayName = DomUtil.AddNode(tr, "td");

  DrawUTCDayNameColumn(utcDay, tdForDayName);
  // Start each graphCSV row with a date like "2010/08/01".
  graphCSV.push(tdForDayName.innerText);

  var tableTd = DomUtil.AddNode(tr, "td");

  tableTd.width = "100%";

  var table = DomUtil.AddNode(tableTd, "table");
  table.cellSpacing = 0;
  table.cellPadding = 0;
  table.width = "100%";

  var tr = DomUtil.AddNode(table, "tr");

  for (var timezone in utcOffsetsMillis) {
    AddPeakColumn(tr,
                  entries,
                  utcDay,
                  utcOffsetsMillis[timezone],
                  graphCSV);
  }
  graphCSV.push("\n");
}

/**
 * @returns {StatusTotals}
 */
function GetStateCountsInRange(runs, timeRange) {
  var statusTotalsSeconds = new StatusTotals();

  var y1 = timeRange.startTime;
  var y2 = timeRange.endTime;

  for (var i = 0; i < runs.length; ++i) {
    var run = runs[i];

    // Basically we have two boxes (x and y), and need to find the overlap.
    var x1 = run.startTime;
    var x2 = run.startTime - run.duration;

    if (x1 > y2 && x2 < y1) {
      var leftEdge = Math.min(x1, y1);
      var rightEdge = Math.max(y2, x2);

      var dt = leftEdge - rightEdge;

      statusTotalsSeconds.Increment(run.entry.GetTreeState(),
                                    DateUtil.MillisToSeconds(dt));
    }
  }

  return statusTotalsSeconds;
}

function AddPeakColumn(tr, entries, utcDay, utcOffsetMillis, graphCSV) {
  var td = DomUtil.AddNode(tr, "td");

  // Width is (100/[items in utcMillisOffsets])%.
  td.width = "25%";
  td.align = "center";

  // Get a day range for the timezone.
  var day = new TimeRange(utcDay.startTime - utcOffsetMillis,
                          utcDay.endTime - utcOffsetMillis);

  // Extract the data from |entries| that apply to |day|, and break it
  // into (start,duration) runs.
  var runs = MakeRuns(entries, day);

  // 9 - 5 in the local timezone.
  var localPeakHours = new TimeRange(
      day.endTime + 17 * DateUtil.MILLIS_PER_HOUR,
      day.endTime + 9 * DateUtil.MILLIS_PER_HOUR);
                                     
  var statusTotalsSeconds = GetStateCountsInRange(runs, localPeakHours);

  var total = statusTotalsSeconds.GetTotalKnown();

  var percentOpenText = "";
  var color = "";
  var className = "";

  var percentOpenNumber = "0.0";
  if (total == 0) {
    // This can happen if the day is in the future (edge day of slow timezone).
    percentOpenText = "N/A";
  } else {
    var fraction = statusTotalsSeconds.GetOpen() / total;
    percentOpenNumber = (100 * fraction).toFixed(2);
    percentOpenText = percentOpenNumber + "%";

    // If we didn't fetch all the data necessary, our percentage won't be
    // accurate as it is missing zones.
    if (total != DateUtil.MillisToSeconds(
          localPeakHours.startTime - localPeakHours.endTime)) {
      percentOpenText += " [incomplete]";
    }

    // Choose a style based on how bad things are.
    var badnessBuckets = [0.50, 0.75, 1.1];
    for (var i = 0; i < badnessBuckets.length; ++i) {
      if (fraction < badnessBuckets[i]) {
        className = "open_badness" + i;
        break;
      }
    }
  }
  graphCSV.push("," + percentOpenNumber);

  var span = DomUtil.AddNode(td, "span");
  span.className = className;
  DomUtil.AddText(span, percentOpenText);
}

/**
 * Draws a specific day's name column in the peak hours charts.
 * @param {TimeRange} utcDay
 * @param {DOMNode} td The column to print name into.
 */
function DrawUTCDayNameColumn(utcDay, td) {
  var d = new Date();
  d.setTime(utcDay.endTime);

  // Display the day as for example "2009/8/38".
  var dateText =
      d.getUTCFullYear() + "/" +
      PadWithZero(d.getUTCMonth() + 1, 2) + "/" +
      PadWithZero(d.getUTCDate(), 2);

  // Color saturday and sunday differently.
  if (d.getUTCDay() == 0) {
    td.className = "sundayName";
  } else if (d.getUTCDay() == 6) {
    td.className = "saturdayName";
  }

  td.innerHTML = dateText;
}

})();  // Private implementation.
