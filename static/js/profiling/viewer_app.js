// Copyright (c) 2011 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * The ProfilingApp encapsulates the application's global state,
 * and controls its subviews.
 *
 * @constructor
 */
function ProfilingApp() {
  // Factories for each of the view types.
  this.viewFactories_ = {
    // TODO(maruel): More views.
    list: CreateListView,
  };

  // Views which have been created so far, keyed by their name.
  this.liveViews_ = {};

  // The last list of entries fetched from the server.
  this.entries_ = null;

  // The last query filters that entries were fetched from the server for.
  this.filters_ = null;

  this.update_timeout_id_ = null;
  this.pending_request_ = null;
  this.filters_names_ = ["platform", "domain", "executable", "first_arg"];

  window.onload.addEventListener(this.OnPageLoaded.bind(this));
}

/**
 * This is the main entry point to the application, when the page has
 * finished loading.
 */
ProfilingApp.prototype.OnPageLoaded = function() {
  this.ApplyQueryParameters();
  this.OnQueryChanged();
};


ProfilingApp.prototype.PostOnQueryChanged = function() {
  if (this.update_timeout_id_ != null) {
    window.clearTimeout(this.update_timeout_id_);
    this.update_timeout_id_ = null;
  }

  var callback = this.OnQueryChanged.bind(this);
  this.update_timeout_id_ = window.setTimeout(callback, 20);
};

/**
 * This method is called whenever the query parameters changed and we need to
 * fetch new data off the server to update the views.
 */
ProfilingApp.prototype.OnQueryChanged = function() {
  if (this.pending_request_ != null) {
    this.pending_request_.abort();
    this.pending_request_ = null;
  }
  if (this.update_timeout_id_ != null) {
    window.clearTimeout(this.update_timeout_id_);
    this.update_timeout_id_ = null;
  }
  var filters = this.GetFilters();

  // Invalidate data derived from the previous filters.
  this.filters_ = null;
  this.entries_ = null;

  // Clear all views.
  for (var i in this.liveViews_) {
    this.ShowView(i, false);
  }
  this.liveViews_ = {};

  // Use AJAX to fetch the tree status data for the new filters.
  // On completion it will call OnDataAvailable() with the data.
  this.SetLoadingIndicator("Fetching data...");
  var callback = this.OnDataAvailable.bind(this, filters);
  this.pending_request_ = DataFetcher.GetEntries(filters, callback);
};

/**
 * This method is called when new data has been received from the server.
 */
ProfilingApp.prototype.OnDataAvailable = function(filters, entries) {
  this.SetLoadingIndicator("");

  // Set the new data as current.
  this.pending_request_ = null;
  this.filters_ = filters;
  this.entries_ = entries;

  if (this.entries_) {
    // Force the view to redraw itself using the new data.
    this.SwitchToView(this.GetCurrentViewName());
  }
};

/**
 * Gets the filters the user is interested in.
 * @return {Stuff}
 */
ProfilingApp.prototype.GetFilters = function() {
  var filters = {};
  for (var i = 0; i < this.filters_names_.length; ++i) {
    var name = this.filters_names_[i];
    var d = document.getElementById(name);
    filters[name] = d.value;
  }
  return filters;
};

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
ProfilingApp.prototype.ApplyQueryParameters = function() {
  var params = GetQueryParameters();
  for (var i = 0; i < this.filters_names_.length; ++i) {
    var d = document.getElementById(this.filters_names_[i]);
    if (this.filters_names_[i] in params) {
      d.value = params[this.filters_names_[i]];
    }
  }
};

/**
 * Updates a part of the UI to show we are waiting for stuff to happen.
 * @param {string} text The message to display.
 */
ProfilingApp.prototype.SetLoadingIndicator = function(text) {
  var d = document.getElementById("loading");
  d.innerHTML = text;
  DomUtil.DisplayNode(d, text != "");
};

/**
 * Gets the name of the currently active view.
 * @return {string}
 */
ProfilingApp.prototype.GetCurrentViewName = function() {
  var previous_view = ClassUtil.FindElementByClassName(
      "viewBadge Selected").match("^(.+)_badge$")[1];
  if (!previous_view) {
    throw "Previous view cannot be found";
  }
  return previous_view;
};

/**
 * Sets |viewName| as the active view.
 * @param {string} viewName
 */
ProfilingApp.prototype.SetCurrentViewName = function(viewName) {
  if (!viewName) {
    throw "Can't switch to undefined";
  }
  ClassUtil.ResetClass("viewBadge", viewName + "_badge", "Selected");
};

/**
 * Switches |viewName| to be the active view.
 * @param {string} viewName
 */
ProfilingApp.prototype.SwitchToView = function(viewName) {
  var prevViewName = this.GetCurrentViewName();
  this.SetCurrentViewName(viewName);

  // Hide the previously active view.
  if (this.liveViews_[prevViewName]) {
    this.ShowView(prevViewName, false);
  }

  // If a view hasn't been created yet for |viewName|, do so.
  if (!this.liveViews_[viewName]) {
    this.liveViews_[viewName] =
        this.viewFactories_[viewName](this.filters_, this.entries_);
  }

  // Show the now active view.
  this.ShowView(viewName, true);
};

/**
 * Generic method to change the styling of the view's tab handle to indicate
 * whether it is active, and to show/hide its content pane.
 * This assumes we have given consistent IDs to the elements.
 *
 * @param {string} viewName
 * @param {boolean} visible
 */
ProfilingApp.prototype.ShowView = function(viewName, visible) {
  var element = document.getElementById(viewName + "_container");
  if (!element) {
    throw "Couldn't find " + viewName;
  }
  DomUtil.DisplayNode(element, visible);
  this.liveViews_[viewName].OnShow(visible);
};
