// Copyright (c) 2011 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Helper utility functions for manipulating the element classes.
 */
var ClassUtil = {};

/**
 * Finds an element based on its class name.
 **/
ClassUtil.FindElementByClassName = function(className) {
  var items = document.getElementsByClassName(className);
  if (items.length != 1) {
    throw "Found " + items.length + " item(s) by class " + className;
  }
  return items[0].id;
};

/**
 * Resets class type of all items except one.
 **/
ClassUtil.ResetClass = function(className, specialId, specialClass) {
  var items = document.getElementsByClassName(className);
  var fail = function(msg) {
    throw "Internal error in ResetClass(" + className + ", " + specialId +
        ", " + specialClass + ")\nEnumerated " + items.length + " items.\n" +
        msg;
  };
  var found;
  for (var i in items) {
    var item = items[i];
    if (item.id == specialId) {
      item.className = className + " " + specialClass;
      if (found) {
        fail("Found 2 times");
      }
      found = i;
    } else {
      item.className = className;
    }
  }
  if (!found) {
    fail("Found 0 time");
  }
};
