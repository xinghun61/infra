// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrConvertIssue} from './mr-convert-issue.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';

let element;
let form;

suite('mr-convert-issue', () => {
  setup(() => {
    element = document.createElement('mr-convert-issue');
    document.body.appendChild(element);

    form = element.shadowRoot.querySelector('#convertIssueForm');
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrConvertIssue);
  });

  test('no template chosen', () => {
    let buttons = element.shadowRoot.querySelectorAll('chops-button');
    assert.isTrue(buttons[buttons.length - 1].disabled);
  });
});
