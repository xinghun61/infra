/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * It is common to make a DIV temporarily visible to simulate
 * a popup window. Often, this is done by adding an onClick
 * handler to the element that can be clicked on to show the
 * popup.
 *
 * Unfortunately, closing the popup is not as simple.
 * The popup creator often wants to let the user close
 * the popup by clicking elsewhere on the window; however,
 * the popup only receives mouse events that occur
 * on the popup itself. Thus, popups need a mechanism
 * that notifies them that the user has clicked elsewhere
 * to try to get rid of them.
 *
 * PopupController is such a mechanism --
 * it monitors all mousedown events that
 * occur in the window so that it can notify registered
 * popups of the mousedown, and the popups can choose
 * to deactivate themselves.
 *
 * For an object to qualify as a popup, it must have a
 * function called "deactivate" that takes a mousedown event
 * and returns a boolean indicating that it has deactivated
 * itself as a result of that event.
 *
 * EXAMPLE:
 *
 * // popup that attaches itself to the supplied div
 * function MyPopup(div) {
 *   this._div = div;
 *   this._isVisible = false;
 *   this._innerHTML = ...
 * }
 *
 * MyPopup.prototype.show = function() {
 *   this._div.display = '';
 *   this._isVisible = true;
 *   PC_addPopup(this);
 * }
 *
 * MyPopup.prototype.hide = function() {
 *   this._div.display = 'none';
 *   this._isVisible = false;
 * }
 *
 * MyPopup.prototype.deactivate = function(e) {
 *   if (this._isVisible) {
 *     var p = GetMousePosition(e);
 *     if (nodeBounds(this._div).contains(p)) {
 *       return false; // use clicked on popup, remain visible
 *     } else {
 *       this.hide();
 *       return true; // clicked outside popup, make invisible
 *     }
 *   } else {
 *     return true; // already deactivated, not visible
 *   }
 * }
 *
 * DEPENDENCIES (from this directory):
 *   bind.js
 *   listen.js
 *   common.js
 *   shapes.js
 *   geom.js
 *
 * USAGE:
 *  _PC_Install() must be called after the body is loaded
 */

/**
 * PopupController constructor.
 * @constructor
 */
function PopupController() {
  this.activePopups_ = [];
}

/**
 * @param {Document} opt_doc document to add PopupController to
 *                   DEFAULT: "document" variable that is currently in scope
 * @return {boolean} indicating if PopupController installed for the document;
 *                   returns false if document already had PopupController
 */
function _PC_Install(opt_doc) {
  if (gPopupControllerInstalled) return false;
  gPopupControllerInstalled = true;
  let doc = (opt_doc) ? opt_doc : document;

  // insert _notifyPopups in BODY's onmousedown chain
  listen(doc.body, 'mousedown', PC_notifyPopups);
  return true;
}

/**
 * Notifies each popup of a mousedown event, giving
 * each popup the chance to deactivate itself.
 *
 * @throws Error if a popup does not have a deactivate function
 *
 * @private
 */
function PC_notifyPopups(e) {
  if (gPopupController.activePopups_.length == 0) return false;
  e = e || window.event;
  for (let i = gPopupController.activePopups_.length - 1; i >= 0; --i) {
    let popup = gPopupController.activePopups_[i];
    PC_assertIsPopup(popup);
    if (popup.deactivate(e)) {
      gPopupController.activePopups_.splice(i, 1);
    }
  }
  return true;
}

/**
 * Adds the popup to the list of popups to be
 * notified of a mousedown event.
 *
 * @return boolean indicating if added popup; false if already contained
 * @throws Error if popup does not have a deactivate function
 */
function PC_addPopup(popup) {
  PC_assertIsPopup(popup);
  for (let i = 0; i < gPopupController.activePopups_.length; ++i) {
    if (popup === gPopupController.activePopups_[i]) return false;
  }
  gPopupController.activePopups_.push(popup);
  return true;
}

/** asserts that popup has a deactivate function */
function PC_assertIsPopup(popup) {
  AssertType(popup.deactivate, Function, 'popup missing deactivate function');
}

var gPopupController = new PopupController();
var gPopupControllerInstalled = false;
