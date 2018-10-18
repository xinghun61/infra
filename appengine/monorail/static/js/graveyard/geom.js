/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

// functions for dealing with layout and geometry of page elements.
// Requires shapes.js

/** returns the bounding box of the given DOM node in document space.
  *
  * @param {Element?} obj a DOM node.
  * @return {Rect?}
  */
function nodeBounds(obj) {
  if (!obj) return null;

  function fixRectForScrolling(r) {
    // Need to take into account scrolling offset of ancestors (IE already does
    // this)
    for (let o = obj.offsetParent;
      o && o.offsetParent;
      o = o.offsetParent) {
      if (o.scrollLeft) {
        r.x -= o.scrollLeft;
      }
      if (o.scrollTop) {
        r.y -= o.scrollTop;
      }
    }
  }

  let refWindow;
  if (obj.ownerDocument && obj.ownerDocument.parentWindow) {
    refWindow = obj.ownerDocument.parentWindow;
  } else if (obj.ownerDocument && obj.ownerDocument.defaultView) {
    refWindow = obj.ownerDocument.defaultView;
  } else {
    refWindow = window;
  }

  // IE, Mozilla 3+
  if (obj.getBoundingClientRect) {
    let rect = obj.getBoundingClientRect();

    return new Rect(rect.left + GetScrollLeft(refWindow),
      rect.top + GetScrollTop(refWindow),
      rect.right - rect.left,
      rect.bottom - rect.top,
      refWindow);
  }

  // Mozilla < 3
  if (obj.ownerDocument && obj.ownerDocument.getBoxObjectFor) {
    let box = obj.ownerDocument.getBoxObjectFor(obj);
    var r = new Rect(box.x, box.y, box.width, box.height, refWindow);
    fixRectForScrolling(r);
    return r;
  }

  // Fallback to recursively computing this
  let left = 0;
  let top = 0;
  for (let o = obj; o.offsetParent; o = o.offsetParent) {
    left += o.offsetLeft;
    top += o.offsetTop;
  }

  var r = new Rect(left, top, obj.offsetWidth, obj.offsetHeight, refWindow);
  fixRectForScrolling(r);
  return r;
}

function GetMousePosition(e) {
  // copied from http://www.quirksmode.org/js/events_compinfo.html
  let posx = 0;
  let posy = 0;
  if (e.pageX || e.pageY) {
    posx = e.pageX;
    posy = e.pageY;
  } else if (e.clientX || e.clientY) {
    let obj = (e.target ? e.target : e.srcElement);
    let refWindow;
    if (obj.ownerDocument && obj.ownerDocument.parentWindow) {
      refWindow = obj.ownerDocument.parentWindow;
    } else {
      refWindow = window;
    }
    posx = e.clientX + GetScrollLeft(refWindow);
    posy = e.clientY + GetScrollTop(refWindow);
  }
  return new Point(posx, posy, window);
}
