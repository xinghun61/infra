/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * This file contains JS utilities used by other JS files in Monorail.
 */


/**
 * Add an indexOf method to all arrays, if this brower's JS implementation
 * does not already have it.
 * @param {Object} item The item to find
 * @returns {number} The index of the given item, or -1 if not found.
 */
if (Array.prototype.indexOf == undefined) {
  Array.prototype.indexOf = function(item) {
    for (var i = 0; i < this.length; ++i) {
      if (this[i] == item) return i;
    }
    return -1;
  }
}


/**
 * This function works around a FF HTML layout problem.  The table
 * width is somehow rendered at 100% when the table contains a
 * display:none element, later, when that element is displayed, the
 * table renders at the correct width.  The work-around is to have the
 * element initiallye displayed so that the table renders properly,
 * but then immediately hide the element until it is needed.
 *
 * TODO(jrobbins): Find HTML markup that FF can render more
 * consistently.  After that, I can remove this hack.
 */
function TKR_forceProperTableWidth() {
 var e = $('confirmarea');
 if (e) e.style.display='none';
}
