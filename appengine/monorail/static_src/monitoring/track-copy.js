/* Copyright 2018 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file.
 */

// This counts copy and paste events.

function labelForElement(el) {
  let label = el.localName;
  if (el.id) {
    label = label + '#' + el.id;
  }
  return label;
}

window.addEventListener('copy', function(evt) {
  const label = labelForElement(evt.srcElement);
  const len = window.getSelection().toString().length;
  ga('send', 'event', window.location.pathname, 'copy', label, len);
});

window.addEventListener('paste', function(evt) {
  const label = labelForElement(evt.srcElement);
  const text = evt.clipboardData.getData('text/plain');
  const len = text ? text.length : 0;
  ga('send', 'event', window.location.pathname, 'paste', label, len);
});
