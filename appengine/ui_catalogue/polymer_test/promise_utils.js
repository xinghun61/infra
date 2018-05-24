// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Standard promises for use in tests
 */
function zeroTimeout() {
  return new Promise(resolve => {
    setTimeout(resolve, 0);
  });
}

function eventPromise(element, event) {
  return new Promise(resolve => {
    element.addEventListener(event, resolve, once=true);
  })
}

function domChanged(el) {
  return eventPromise(el, 'dom-change');
}

