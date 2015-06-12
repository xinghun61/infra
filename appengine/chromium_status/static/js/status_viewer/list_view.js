// Copyright (c) 2009 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Factory function to create a View for seeing closure/open events as a flat
 * list.
 */
var CreateListView;

// -----------------------------------------------------------------------------
// Private implementation
// -----------------------------------------------------------------------------

(function() {

CreateListView = function(timeRange, entries) {
  return new ListView(timeRange, entries);
};

function ListView(timeRange, entries) {
  var parent = document.getElementById("list_tbody");
  DrawListView(parent, timeRange, entries);
}

ListView.prototype.Show = function(visible) {
 gViewerApp.ShowViewContentAndTabArea('list', visible);
};

function DrawListView(parent, timeRange, entries) {
  parent.innerHTML = "";

  var runs = MakeRuns(entries, timeRange);

  for (var i = 0; i < runs.length; ++i) {
    var entry = runs[i].entry;

    // Skip the magic entry we added to the run to fill gap.
    if (entry.IsOracle())
      continue;

    var tr = DomUtil.AddNode(parent, "tr");
    var tdDate = DomUtil.AddNode(tr, "td");
    var tdAuthor = DomUtil.AddNode(tr, "td");
    var tdMessage = DomUtil.AddNode(tr, "td");
    var tdType = DomUtil.AddNode(tr, "td");

    DomUtil.AddText(tdDate, DateUtil.FormatAsLocalDate(entry.timestamp));
    DomUtil.AddText(tdAuthor, entry.author);
    DomUtil.AddText(tdMessage, entry.message);
    DomUtil.AddText(tdType, entry.GetTreeState());

    tdType.className = entry.GetTreeState();
  }
}

})();  // Private implementation.
