// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import {MrCodeFontToggle} from './mr-code-font-toggle.js';

let element;
let ancestor;

suite('mr-code-font-toggle', () => {

  setup(() => {
    element = document.createElement('mr-code-font-toggle');
    document.body.appendChild(element);
    ancestor = document.createElement('div');
    ancestor.id = 'color_control';
    document.body.appendChild(ancestor);
  });

  teardown(() => {
    document.body.removeChild(element);
    document.body.removeChild(ancestor);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrCodeFontToggle);
  });

  test('clicking toggles the codefont CSS class', () => {
    var chopsToggle = element.shadowRoot.querySelector('chops-toggle');
    var label = chopsToggle.shadowRoot.querySelector('label');

    // code font is initially off.
    assert.isFalse(ancestor.classList.contains('codefont'));
    label.click();  // Toggle it on.
    assert.isTrue(ancestor.classList.contains('codefont'));
    label.click();  // Toggle it off.
    assert.isFalse(ancestor.classList.contains('codefont'));
  });
});
