/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * Functions used by the Project Hosting to control the display of
 * elements on the page, rollovers, and popup menus.
 *
 * Most of these functions are extracted from dit-display.js
 */


/**
 * Hide the HTML element with the given ID.
 * @param {string} id The HTML element ID.
 * @return {boolean} Always returns false to cancel the browser event
 *     if used as an event handler.
 */
function CS_hideID(id) {
  $(id).style.display = 'none';
  return false;
}


/**
 * Show the HTML element with the given ID.
 * @param {string} id The HTML element ID.
 * @return {boolean} Always returns false to cancel the browser event
 *     if used as an event handler.
 */
function CS_showID(id) {
  $(id).style.display = '';
  return false;
}


/**
 * Hide the given HTML element.
 * @param {Element} el The HTML element.
 * @return {boolean} Always returns false to cancel the browser event
 *     if used as an event handler.
 */
function CS_hideEl(el) {
  el.style.display = 'none';
  return false;
}


/**
 * Show the given HTML element.
 * @param {Element} el The HTML element.
 * @return {boolean} Always returns false to cancel the browser event
 *     if used as an event handler.
 */
function CS_showEl(el) {
  el.style.display = '';
  return false;
}


/**
 * Show one element instead of another.  That is to say, show a new element and
 * hide an old one.  Usually the element is the element that the user clicked
 * on with the intention of "expanding it" to access the new element.
 * @param {string} newID The ID of the HTML element to show.
 * @param {Element} oldEl The HTML element to hide.
 * @return {boolean} Always returns false to cancel the browser event
 *     if used as an event handler.
 */
function CS_showInstead(newID, oldEl) {
  $(newID).style.display = '';
  oldEl.style.display = 'none';
  return false;
}

/**
 * Toggle the open/closed state of a section of the page.  As a result, CSS
 * rules will make certain elements displayed and other elements hidden.  The
 * section is some HTML element that encloses the element that the user clicked
 * on.
 * @param {Element} el The element that the user clicked on.
 * @return {boolean} Always returns false to cancel the browser event
 *     if used as an event handler.
 */
function CS_toggleHidden(el) {
  while (el) {
    if (el.classList.contains('closed')) {
      el.classList.remove('closed');
      el.classList.add('opened');
      return false;
    }
    if (el.classList.contains('opened')) {
      el.classList.remove('opened');
      el.classList.add('closed');
      return false;
    }
    el = el.parentNode;
  }
}


/**
 * Toggle the expand/collapse state of a section of the page.  As a result, CSS
 * rules will make certain elements displayed and other elements hidden.  The
 * section is some HTML element that encloses the element that the user clicked
 * on.
 * TODO(jrobbins): eliminate redundancy with function above.
 * @param {Element} el The element that the user clicked on.
 * @return {boolean} Always returns false to cancel the browser event
 *     if used as an event handler.
 */
function CS_toggleCollapse(el) {
  while (el) {
    if (el.classList.contains('collapse')) {
      el.classList.remove('collapse');
      el.classList.add('expand');
      return false;
    }
    if (el.classList.contains('expand')) {
      el.classList.remove('expand');
      el.classList.add('collapse');
      return false;
    }
    el = el.parentNode;
  }
}


/**
 * Register a function for mouse clicks on the results table.  We
 * listen on the table to avoid adding 1000 individual listeners on
 * the cells.  This is needed because some browsers (now including
 * Chrome) do not generate click events for mouse buttons other than
 * the primary mouse button.  Chrome and Firefox generate auxclick
 * events, but Edge does not.
 */

function CS_addClickListener(tableEl, handler) {
  function maybeClick(event) {
    const target = getTargetFromEvent(event);

    const inLink = target.tagName == 'A' || target.parentNode.tagName == 'A';

    if (inLink && !target.classList.contains('computehref')) {
      // The <a> elements already have the correct hrefs.
      return;
    }
    if (event.button == 2) {
      // User is trying to open a context menu, not trying to navigate.
      return;
    }

    let td = target;
    while (td && td.tagName != 'TD' && td.tagName != 'TH') {
      td = td.parentNode;
    }
    if (td.classList.contains('rowwidgets')) {
      // User clicked on a checkbox.
      return;
    }
    // User clicked on an issue ID link or text or cell.
    event.preventDefault();
    handler(event);
  }
  tableEl.addEventListener('click', maybeClick);
  tableEl.addEventListener('auxclick', maybeClick);
}

function getTargetFromEvent(event) {
  let target = event.target || event.srcElement;
  if (target.shadowRoot) {
  // Find the element within the shadowDOM.
    const path = event.path || event.composedPath();
    target = path[0];
  }
  return target;
}


// Exports
_hideID = CS_hideID;
_showID = CS_showID;
_hideEl = CS_hideEl;
_showEl = CS_showEl;
_showInstead = CS_showInstead;
_toggleHidden = CS_toggleHidden;
_toggleCollapse = CS_toggleCollapse;
_addClickListener = CS_addClickListener;
