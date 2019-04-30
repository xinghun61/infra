// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrConvertIssue} from './mr-convert-issue.js';

let element;

suite('mr-convert-issue', () => {
  setup(() => {
    element = document.createElement('mr-convert-issue');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrConvertIssue);
  });

  test('no template chosen', async () => {
    await element.updateComplete;

    const buttons = element.shadowRoot.querySelectorAll('chops-button');
    assert.isTrue(buttons[buttons.length - 1].disabled);
  });
});
