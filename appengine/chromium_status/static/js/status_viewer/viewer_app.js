// Copyright (c) 2009 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * The TreeStatusViewerApp encapsulates the application's global state,
 * and controls its subviews.
 *
 * @constructor
 */
function TreeStatusViewerApp() {
  // Factories for each of the view types.
  this.viewFactories_ = {
    fragmentation: CreateFragmentationView,
    stats: CreateStatsView,
    list: CreateListView,
    peak: CreatePeakHoursView
  };

  // Views which have been created so far, keyed by their name.
  this.liveViews_ = {};

  // The last list of entries fetched from the server.
  this.entries_ = null;

  // The last time range that entries were fetched from the server for.
  this.timeRange_ = null;
}

/**
 * This is the main entry point to the application, when the page has
 * finished loading.
 */
TreeStatusViewerApp.prototype.OnPageLoaded = function() {
  // Look for any parameters in the query string that we recognize,
  // and apply them to change the UI accordingly.
  // (For example update the "Start date" input box).
  this.ApplyQueryParameters();

  // Trigger fetch of data from server.
  this.OnTimeRangeChanged();
}

/**
 * This method is called whenever the window of time has been changed
 * and we need to fetch new data off the server to update the views.
 */
TreeStatusViewerApp.prototype.OnTimeRangeChanged = function() {
  var timeRange = this.GetTimeRange();

  // Invalidate data derived from the previous time range.
  this.timeRange = null;
  this.entries_ = null;
  this.liveViews_ = {};

  // Use AJAX to fetch the tree status data for the new time range.
  // On completion it will call OnDataAvailable() with the data.
  this.SetLoadingIndicator("Fetching data...");
  var callback = this.OnDataAvailable.bind(this, timeRange);
  DataFetcher.GetTreeStatusEntries(timeRange, callback);
}

/**
 * This method is called when new data has been received from the server.
 */
TreeStatusViewerApp.prototype.OnDataAvailable = function(timeRange, entries) {
  this.SetLoadingIndicator("");

  // Set the new data as current.
  this.timeRange_ = timeRange;
  this.entries_ = entries;

  // Force the view to redraw itself using the new data.
  this.SwitchToView(this.GetCurrentViewName());
}

/**
 * Gets the range of time the user is interested in.
 * @return {TimeRange}
 */
TreeStatusViewerApp.prototype.GetTimeRange = function() {
  var input = document.getElementById('startTime');
  var d = DateUtil.ParseStringToLocalDate(input.value);
  if (!d) {
    d = new Date();  // Assume current day
    d.setHours(0);
    d.setMinutes(0);
    d.setMinutes(0);
    d.setSeconds(0);
    d.setMilliseconds(0);
  }

  var startTime = d.getTime() + DateUtil.MILLIS_PER_DAY;

  input = document.getElementById('numDays');
  var numDays = parseInt(input.value, 10);
  var endTime = startTime - DateUtil.MILLIS_PER_DAY * numDays;

  return new TimeRange(startTime, endTime);
}

/**
 * Gets the current window's URL's query parameters, as a
 * dictionary of key/value pairs.
 *
 * @return {Object} Dictionary of name/value pairs.
 */
function GetQueryParameters() {
  var values = {};
  if (window.location.search) {
    params = window.location.search.substr(1).split("&");
    for (var i = 0; i < params.length; ++i) {
      var parts = params[i].split("=");
      if (parts.length == 2) {
        values[parts[0]] = decodeURIComponent(parts[1]);
      }
    }
  }
  return values;
}

/**
 * Checks the URL for query parameters, and applies any with meaning to us.
 */
TreeStatusViewerApp.prototype.ApplyQueryParameters = function() {
  var formNames = ["startTime", "numDays", "curView"];

  var params = GetQueryParameters();

  for (var i = 0; i < formNames.length; ++i) {
    var d = document.getElementById(formNames[i]);
    if (formNames[i] in params) {
      d.value = params[formNames[i]];
    }
  }
}

/**
 * Updates a part of the UI to show we are waiting for stuff to happen.
 * @param {string} text The message to display.
 */
TreeStatusViewerApp.prototype.SetLoadingIndicator = function(text) {
  var d = document.getElementById("loading");
  d.innerHTML = text;
  DomUtil.DisplayNode(d, text != "");
}

/**
 * Gets the name of the currently active view.
 * @return {string}
 */
TreeStatusViewerApp.prototype.GetCurrentViewName = function() {
  return document.getElementById("curView").value;
}

/**
 * Sets |viewName| as the active view.
 * @param {string} viewName
 */
TreeStatusViewerApp.prototype.SetCurrentViewName = function(viewName) {
  document.getElementById("curView").value = viewName;
}

/**
 * Switches |viewName| to be the active view.
 * @param {string} viewName
 */
TreeStatusViewerApp.prototype.SwitchToView = function(viewName) {
  var prevViewName = this.GetCurrentViewName();
  this.SetCurrentViewName(viewName);

  // Hide the previously active view.
  if (this.liveViews_[prevViewName]) {
    this.liveViews_[prevViewName].Show(false);
  }

  // If a view hasn't been created yet for |viewName|, do so.
  if (!this.liveViews_[viewName]) {
    this.liveViews_[viewName] =
        this.viewFactories_[viewName](this.timeRange_, this.entries_);
  }

  // Show the now active view.
  this.liveViews_[viewName].Show(true);
}

/**
 * Generic method to change the styling of the view's tab handle to indicate
 * whether it is active, and to show/hide its content pane.
 * This assumes we have given consistent IDs to the elements.
 *
 * @param {string} viewName
 * @param {boolean} visible
 */
TreeStatusViewerApp.prototype.ShowViewContentAndTabArea =
    function(viewName, visible) {
  DomUtil.DisplayNode(document.getElementById(viewName + "_container"),
                      visible);

  var badgeClass = visible ? "viewBadge_selected" : "viewBadge";
  document.getElementById(viewName + "_badge").className = badgeClass;
}
