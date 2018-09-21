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
 * Register a function for mouse clicks on a table row.  This is needed because
 * some browsers (now including Chrome) do not generate click events for mouse
 * buttons other than the primary mouse button.  So, we look for a mousedown
 * and mouseup at about the same location.
 */

var CS_lastX = 0, CS_lastY = 0;

function CS_addClickListener(tableEl, handler) {
  tableEl.addEventListener('click', function(event) {
    if (event.target.classList.contains('computehref') &&
        (event.button == 0 || event.button == 1)) {
	event.preventDefault();
    }
    if (event.target.tagName == 'A') {
      return;
    }
    if (event.button == 1) {
      event.preventDefault();
    }
  });
  tableEl.addEventListener('mousedown', function(event) {
    if (event.target.tagName == 'A' &&
        !event.target.classList.contains('computehref')) {
      return;
    }
    CS_lastX = event.clientX;
    CS_lastY = event.clientY;
    if (event.button == 1) {
      event.preventDefault();
    }
  });
  tableEl.addEventListener('mouseup', function(event) {
    if (event.target.tagName == 'A' &&
        !event.target.classList.contains('computehref')) {
      return;
    }
    if (CS_lastX - 2 < event.clientX && CS_lastX + 2 > event.clientX &&
        CS_lastY - 2 < event.clientY && CS_lastY + 2 > event.clientY) {
      handler(event);
    }
  });
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
