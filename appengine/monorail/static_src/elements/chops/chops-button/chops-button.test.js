// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {ChopsButton} from './chops-button.js';
import {auditA11y} from 'shared/test-helpers';

let element;

describe('chops-button', () => {
  beforeEach(() => {
    element = document.createElement('chops-button');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, ChopsButton);
  });

  it('initial a11y', async () => {
    const text = document.createTextNode('button text');
    element.appendChild(text);
    await auditA11y(element);
  });

  it('chops-button can be disabled', async () => {
    assert.isFalse(element.hasAttribute('disabled'));

    element.disabled = true;
    await element.updateComplete;

    assert.isTrue(element.hasAttribute('disabled'));
  });
});
