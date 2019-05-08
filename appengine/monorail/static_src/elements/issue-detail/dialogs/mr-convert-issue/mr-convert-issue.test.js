// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrConvertIssue} from './mr-convert-issue.js';

let element;

describe('mr-convert-issue', () => {
  beforeEach(() => {
    element = document.createElement('mr-convert-issue');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrConvertIssue);
  });

  it('no template chosen', async () => {
    await element.updateComplete;

    const buttons = element.shadowRoot.querySelectorAll('chops-button');
    assert.isTrue(buttons[buttons.length - 1].disabled);
  });
});
