// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import sinon from 'sinon';
import {assert} from 'chai';
import {MrModeSelector} from './mr-mode-selector.js';

let element;

describe('mr-mode-selector', () => {
  beforeEach(() => {
    element = document.createElement('mr-mode-selector');
    document.body.appendChild(element);

    element._page = sinon.stub();
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrModeSelector);
  });

  it('changing mode causes page navigation', async () => {
    element.value = 'list';
    element.projectName = 'chromium';

    await element.updateComplete;

    element.setValue('grid');

    sinon.assert.calledOnce(element._page);
    sinon.assert.calledWith(element._page, '/p/chromium/issues/list?mode=grid');
  });

  it('changing mode to list deletes mode param', async () => {
    element.value = 'grid';
    element.projectName = 'chromium';

    await element.updateComplete;

    element.setValue('list');

    sinon.assert.calledOnce(element._page);
    sinon.assert.calledWith(element._page, '/p/chromium/issues/list');
  });
});
