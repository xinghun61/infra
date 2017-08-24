/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * This file contains JS functions that implement various navigation
 * features of Monorail.
 */


/**
 * Navigate the browser to the given URL.
 * @param {string} url The URL of the page to browse.
 * @param {boolean} newWindow Open a new tab or window.
 */
function TKR_go(url, newWindow) {
  if (newWindow)
    window.open(url, '_blank');
  else
    document.location = url;
}


/**
 * Tell the browser to scroll to the given anchor on the current page.
 * @param {string} anchor Name of the <a name="xxx"> anchor on the page.
 */
function TKR_goToAnchor(anchor) {
 document.location.hash = anchor;
}


/**
 * Get the user-editable colspec form field.  This text field is normally
 * display:none, but it is shown when the user chooses "Edit columns...".
 * We need a function to get this element because there are multiple form
 * fields on the page with name="colspec", and an IE misfeature sets their
 * id attributes as well, which makes document.getElementById() fail.
 * @return {Element} user editable colspec form field.
 */
function TKR_getColspecElement() {
 return document.getElementById('colspec_field').firstChild;
}


/**
 * Get the hidden form field for colspec.  This is a type="hidden" input field
 * that is submitted as part of the artfact search query.  We need a
 * function to get this element because there are multiple form fields on the
 * page with name="colspec", and an IE misfeature sets their id attributes
 * as well, which makes document.getElementById() fail.
 * @return {Element} colspec hidden form field.
 */
function TKR_getSearchColspecElement() {
 return document.getElementById('search_colspec').firstChild;
}


/**
 * Get the artifact search form field.  This is a visible text field where
 * the user enters a query for issues. This function
 * is needed because there is also the project search field on the each page,
 * and it has name="q".  An IE misfeature confuses name="..." with id="...".
 * @return {Element} artifact query form field, or undefined.
 */
function TKR_getArtifactSearchField() {
  var qq = document.getElementById('qq');
  return qq ? qq.firstChild : undefined;
}


/**
 * Resize the artifiact search box to be bigger when the user has a long
 * query.
 */
var MAX_ARTIFACT_SEARCH_FIELD_SIZE = 75;
var AUTOSIZE_STEP = 3;

function TKR_autosizeArtifactSerchField() {
  var qq = TKR_getArtifactSearchField();
  if (qq) {
    var new_size = qq.value.length + AUTOSIZE_STEP;
    if (new_size > MAX_ARTIFACT_SEARCH_FIELD_SIZE) {
      new_size = MAX_ARTIFACT_SEARCH_FIELD_SIZE;
    }
    if (new_size > qq.size) {
      qq.size = new_size;
    }
  }
}

window.setInterval(TKR_autosizeArtifactSerchField, 700);


/**
 * Build a query string for all the common contextual values that we use.
 */
function TKR_formatContextQueryArgs() {
  var args = "";
  var colspec = TKR_getColspecElement().value;
  if (_ctxHotlistID != "") args += "&hotlist_id=" + _ctxHotlistID;
  if (_ctxCan != 2) args += "&can=" + _ctxCan;
  args += "&q=" + encodeURIComponent(_ctxQuery);
  if (_ctxSortspec != "") args += "&sort=" + _ctxSortspec;
  if (_ctxGroupBy != "") args += "&groupby=" + _ctxGroupBy;
  if (colspec != _ctxDefaultColspec) args += "&colspec=" + colspec;
  if (_ctxStart != 0) args += "&start=" + _ctxStart;
  if (_ctxNum != _ctxResultsPerPage) args += "&num=" + _ctxNum;
  return args;
}

// Fields that should use ":" when filtering.
var _PRETOKENIZED_FIELDS = [
    'owner', 'reporter', 'cc', 'commentby', 'component'];

/**
 * The user wants to narrow his/her search results by adding a search term
 * for the given prefix and value. Reload the issue list page with that
 * additional search term.
 * @param {string} prefix Field or label prefix, e.g., "Priority".
 * @param {string} suffix Field or label value, e.g., "High".
 */
function TKR_filterTo(prefix, suffix) {
  var newQuery = TKR_getArtifactSearchField().value;
  if (newQuery != '') newQuery += ' ';

  var op = '=';
  for (var i = 0; i < _PRETOKENIZED_FIELDS.length; i++) {
    if (prefix == _PRETOKENIZED_FIELDS[i]) {
      op = ':';
      break;
    }
  }

  newQuery += prefix + op + suffix;
  var url = 'list?can=' + $('can').value + '&q=' + newQuery;
  if ($('sort') && $('sort').value) url += '&sort=' + $('sort').value;
  url += '&colspec=' + TKR_getColspecElement().value;
  TKR_go(url);
}


/**
 * The user wants to sort his/her search results by adding a sort spec
 * for the given column. Reload the issue list page with that
 * additional sort spec.
 * @param {string} colname Field or label prefix, e.g., "Priority".
 * @param {boolean} descending True if the values should be reversed.
 */
function TKR_addSort(colname, descending) {
  var existingSortSpec = '';
  if ($('sort')) { existingSortSpec = $('sort').value; }
  var oldSpecs = existingSortSpec.split(/ +/);
  var sortDirective = colname;
  if (descending) sortDirective = '-' + colname;
  var specs = [sortDirective];
  for (var i = 0; i < oldSpecs.length; i++) {
    if (oldSpecs[i] != "" && oldSpecs[i] != colname &&
        oldSpecs[i] != '-' + colname) {
      specs.push(oldSpecs[i])
    }
  }

  var isHotlist = window.location.href.includes('/hotlists/');
  var url = isHotlist ? ($('hotlist_name').value + '?') : ('list?');
  url  += ('can='+ $('can').value + '&q=' +
      TKR_getArtifactSearchField().value);

  url += '&sort=' + specs.join('+');
  url += '&colspec=' + TKR_getColspecElement().value;
  TKR_go(url)
}

/** Convenience function for sorting in ascending order. */
function TKR_sortUp(colname) {
  TKR_addSort(colname, false);
}

/** Convenience function for sorting in descending order. */
function TKR_sortDown(colname) {
  TKR_addSort(colname, true);
}
