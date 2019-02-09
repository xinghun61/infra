// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrInlineEditor} from './mr-inline-editor.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';


let element;

suite('mr-inline-editor', () => {
  setup(() => {
    element = document.createElement('mr-inline-editor');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrInlineEditor);
  });

  test('toggling checkbox toggles sendEmail', () => {
    element.editing = true;
    element.sendEmail = false;

    flush();

    const checkbox = element.shadowRoot.querySelector('#sendEmail');

    checkbox.click();
    assert.equal(checkbox.checked, true);
    assert.equal(element.sendEmail, true);

    checkbox.click();
    assert.equal(checkbox.checked, false);
    assert.equal(element.sendEmail, false);

    checkbox.click();
    assert.equal(checkbox.checked, true);
    assert.equal(element.sendEmail, true);
  });
});
