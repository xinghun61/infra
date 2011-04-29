// Copyright (c) 2009 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Helper utility functions for manipulating the DOM.
 */
var DomUtil = {};

/**
 * Toggles the visibility on a node.
 *
 * @param {DOMNode} n The node to show/hide.
 * @param {boolean} display False to hide the node.
 */
DomUtil.DisplayNode = function(n, display) {
  n.style.display = display ? "" : "none";
}

/**
 * Appends a new node with tag |type| to |parent|.
 *
 * @param {DOMNode} parent
 * @param {string} type
 * @return {DOMNode} The node that was just created.
 */
DomUtil.AddNode = function(parent, type) {
  var doc = parent.ownerDocument;
  var n = doc.createElement(type);
  parent.appendChild(n);
  return n;
}

/**
 * Adds text to node |parent|.
 *
 * @param {DOMNode} parent
 * @param {string} text
 */
DomUtil.AddText = function(parent, text) {
  var doc = parent.ownerDocument;
  var n = doc.createTextNode(text);
  parent.appendChild(n);
  return n;
}
