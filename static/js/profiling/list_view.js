// Copyright (c) 2011 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Factory function to create a View for seeing profiling events as a flat list.
 */
var CreateListView;

// -----------------------------------------------------------------------------
// Private implementation
// -----------------------------------------------------------------------------

(function() {

CreateListView = function(filters, entries) {
  return new ListView(filters, entries);
};

function ListView(filters, entries) {
  this.parent_ = document.getElementById("list_container");
  this.entries_ = entries;
  this.filters_ = filters;
  this.headers_ = [
      "timestamp",
      "domain",
      "executable",
      "first_arg",
      "platform",
      "duration"
  ];
  this.titles_ = [
      "Timestamp",
      "Domain",
      "Executable",
      "First arg",
      "Platform",
      "Duration (s)"
  ];
  this.Draw(this.headers_[0]);
}

ListView.prototype.OnShow = function(visible) {
};

/**
 * Sort by |viewName| to be the active view.
 * @param {string} viewName
 */
ListView.prototype.SortBy = function(current_sort) {
  ClassUtil.ResetClass("sortBadge", current_sort + "_badge", "Selected");
  this.Draw(current_sort);
};

ListView.prototype.Draw = function(current_sort) {
  this.SortEntries(current_sort);
  this.parent_.innerHTML = "";
  var table = DomUtil.AddNode(this.parent_, "table");
  table.className = "entriesList";
  var thead = DomUtil.AddNode(table, "thead");
  for (var i in this.headers_) {
    var extra = "";
    var key = this.headers_[i];
    if (key == current_sort) {
      extra = " Selected";
    }
    var th = DomUtil.AddNode(thead, "th");
    th.className = "sortBadge" + extra;
    th.id = key + "_badge";
    var a = DomUtil.AddNode(th, "a");
    a.onclick = this.SortBy.bind(this, key);
    DomUtil.AddText(a, this.titles_[i]);
  }
  var tbody = DomUtil.AddNode(table, "tbody");
  if (!this.entries_) {
    return;
  }
  for (var i = 0; i < this.entries_.length; ++i) {
    var entry = this.entries_[i];
    var tr = DomUtil.AddNode(tbody, "tr");
    var tdTimestamp = DomUtil.AddNode(tr, "td");
    var tdDomain = DomUtil.AddNode(tr, "td");
    var tdExecutable = DomUtil.AddNode(tr, "td");
    var tdFirstArg = DomUtil.AddNode(tr, "td");
    var tdPlatform = DomUtil.AddNode(tr, "td");
    var tdDuration = DomUtil.AddNode(tr, "td");

    DomUtil.AddText(tdTimestamp, DateUtil.FormatLocaleISO(entry.timestamp));
    DomUtil.AddText(tdDomain, entry.domain);
    DomUtil.AddText(tdExecutable, entry.executable);
    DomUtil.AddText(tdFirstArg, entry.first_arg);
    DomUtil.AddText(tdPlatform, entry.platform);
    DomUtil.AddText(tdDuration, entry.duration.toFixed(1));
  }
};

ListView.prototype.SortEntries = function (current_sort) {
  if (this.entries_ != null) {
    this.entries_.sort(function(a, b) {
        var lhs = a[current_sort];
        var rhs = b[current_sort];
        if (typeof lhs != typeof rhs) {
          throw typeof lhs + " != " + typeof rhs;
        }
        if (typeof lhs == "number") {
          return lhs - rhs;
        }
        return lhs.toString().localeCompare(rhs.toString());
      });
  }
};

})();  // Private implementation.

CreateListView.display_name = "List view";
