// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import {ChopsToggle} from './chops-toggle.js';

let element;

suite('chops-toggle', () => {

  setup(() => {
    element = document.createElement('chops-toggle');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, ChopsToggle);
  });

  test('clicking toggle dispatches checked-change event', () => {
    element.checked = false;
    sinon.stub(window, 'CustomEvent');
    sinon.stub(element, 'dispatchEvent');

    element.shadowRoot.querySelector('#checkbox').click();

    assert.deepEqual(window.CustomEvent.args[0][0], 'checked-change');
    assert.deepEqual(window.CustomEvent.args[0][1], {
      detail: {checked: true},
    });

    assert.isTrue(window.CustomEvent.calledOnce);
    assert.isTrue(element.dispatchEvent.calledOnce);

    window.CustomEvent.restore();
    element.dispatchEvent.restore();
  });
});
