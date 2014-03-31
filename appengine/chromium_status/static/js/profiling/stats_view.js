// Copyright (c) 2011 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Factory function to create a View for seeing statistics about profiling
 * events.
 */
var CreateStatsView;

// -----------------------------------------------------------------------------
// Private implementation
// -----------------------------------------------------------------------------

(function() {

CreateStatsView = function(filters, entries) {
  return new StatsView(filters, entries);
};

function StatsView(filters, entries) {
  this.parent_ = document.getElementById("stats_container");
  this.entries_ = entries;
  this.filters_ = filters;
  this.Draw();
}

StatsView.prototype.OnShow = function(visible) {
};

StatsView.prototype.Draw = function() {
  this.parent_.innerHTML = "";
  DomUtil.AddText(this.parent_, "TODO(maruel)");
};

})();  // Private implementation.

CreateStatsView.display_name = "Stats view";
