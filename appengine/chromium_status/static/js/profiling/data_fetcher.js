// Copyright (c) 2011 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Helper that fetches the profiling information data from a server.
 *
 * The public method it exports is:
 *   DataFetcher.GetEntries(filters, callback) method.
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
function Fetch(url, callback, no_cache) {
  DomUtil.DisplayNode(document.getElementById('error_container'), false);
  var r = new XMLHttpRequest();
  r.open("GET", url, true);
  if (no_cache) {
    r.setRequestHeader("pragma", "no-cache");
    r.setRequestHeader("cache-control", "no-cache");
  }
  r.onreadystatechange = function() {
    if (r.readyState == 4) {
      var error;
      if (r.status != 200) {
        error = url + ": " + r.status + ": " + r.statusText;
      } else if (!r.responseText) {
        error = url + ": null response";
      }
      callback(r.responseText, r.status, error);
    }
  }

  r.send(null);
  return r;
};

/**
 * Parses response text and returns the parsed entries.
 */
function ParseDataResponseAndAppend(text) {
  try {
    var content = JSON.parse(text);
  } catch (err) {
    Log("Content is invalid: " + err + "\n" + text);
    return;
  }

  var entries = [];
  for (var i = 0; i < content.length; ++i) {
    var item = content[i];
    entries.push(
      new Entry(
        // The time has a trailing ".XXXXX" ms component we don't care for.
        // Also append "UTC" so we are left with a string resembling:
        // "2009-10-14 21:59:18 UTC"
        DateUtil.ParseUTCDateTimeString(item.timestamp.split(".")[0] + " UTC"),
        item.domain,
        item.platform,
        item.duration,
        item.argv,
        item.executable,
        item.first_arg));
  }
  return entries;
};

/**
 * Fetches all of the profiling data relating to |filters|.
 * On completion |callback(entries)| is invoked, where |entries| is a list of
 * Entry instances or undefined if the request failed.
 **/
DataFetcher.GetEntries = function(filters, callback) {
  var url = "/profiling?";
  var keys = Object.keys(filters);
  for (var i = 0; i < keys.length; i++) {
    var key = keys[i];
    if (filters[key]) {
      if (!url.match("\\?$")) {
        url += "&";
      }
      url += encodeURIComponent(key) + "=" + encodeURIComponent(filters[key]);
    }
  }

  return Fetch(url, OnFetchedDataComplete.bind(this, callback));
};

/**
 * Callback for when the data has been fetched.
 *
 * @param {function} callback The user's callback.
 * @param {string} text The contents of the response.
 * @param {int} status The http status code.
 * @param {string} error Any error message, or undefined on success.
 */
function OnFetchedDataComplete(callback, text, status, error) {
  if (status == 200) {
    // Everything is OK.
    var entries = ParseDataResponseAndAppend(text, error);
    callback(entries);
    if (!entries) {
      // Text is probably an error message. Replace the "log" div with "text"
      // content.
      var log_div = document.getElementById('log');
      log_div.innerText = "";
      DomUtil.AddText(log_div, text);
    }

  } else if (status == 0) {
    // Request was aborted.
    callback(undefined);

  } else if (status == 403) {
    // Need admin access.
    callback(undefined);
    if (!document.getElementById("form_login")) {
      // POST to /login to get a ASCID cookie.
      var container = document.getElementById("login_container");
      var form = DomUtil.AddNode(container, "form");
      form.setAttribute("method", "POST");
      form.setAttribute("action", "/login");
      form.id = "form_login";
      // TODO(maruel): Use a <a> instead? It would be nicer.
      var input = DomUtil.AddNode(form, "input");
      input.type = "submit";
      input.value = "Please login first with an admin account";
      DomUtil.DisplayNode(container, true);
    }

  } else if (status == 500 || status == 501 || status == 503) {
    // AppEngine misbehaves. Dump the text so the user can view the GAE error.
    callback(undefined);
    var container = document.getElementById('error_container');
    container.innerHTML = text;
    DomUtil.DisplayNode(container, true);

  } else {
    // Unknown error. Log it instead of putting it in error_container.
    callback(undefined);
    Log(error);
    Log(text);
  }
};

})();  // Private implementation.
