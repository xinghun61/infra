// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import {ChopsChip} from './chops-chip.js';

let element;

describe('chops-chip', () => {
  beforeEach(() => {
    element = document.createElement('chops-chip');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, ChopsChip);
  });

  it('icon is visible when defined', async () => {
    await element.updateComplete;
    assert.isNull(element.shadowRoot.querySelector('button'));

    element.icon = 'close';

    await element.updateComplete;

    assert.isNotNull(element.shadowRoot.querySelector('button'));
  });

  it('clicking icon fires event', async () => {
    const onClickStub = sinon.stub();

    element.icon = 'close';

    await element.updateComplete;

    element.addEventListener('click-icon', onClickStub);

    assert.isFalse(onClickStub.calledOnce);

    const icon = element.shadowRoot.querySelector('button');
    icon.click();

    assert.isTrue(onClickStub.calledOnce);
  });
});
