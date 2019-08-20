// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import sinon from 'sinon';
import {assert} from 'chai';
import {MrGridControls} from './mr-grid-controls.js';

let element;

describe('mr-grid-controls', () => {
  beforeEach(() => {
    element = document.createElement('mr-grid-controls');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrGridControls);
  });

  it('selection creates url params', async () => {
    await element.updateComplete;

    const dropdownRows = element.shadowRoot.querySelector('.rows');
    const dropdownCols = element.shadowRoot.querySelector('.cols');

    const stub = sinon.stub(element, '_changeUrlParams');

    dropdownRows.selection = 'Status';
    dropdownRows.dispatchEvent(new Event('change'));
    sinon.assert.calledWith(stub, {x: 'None', y: 'Status'});

    dropdownCols.selection = 'Blocking';
    dropdownCols.dispatchEvent(new Event('change'));
    sinon.assert.calledWith(stub, {x: 'Blocking', y: 'Status'});
  });

  it('button selection creates url params', async () => {
    await element.updateComplete;

    const cellsToggle = element.shadowRoot.querySelector('.cell-selector');

    const stub = sinon.stub(element, '_changeUrlParams');

    cellsToggle.value = 'ids';
    cellsToggle.dispatchEvent(new Event('change'));
    sinon.assert.calledWith(stub,
        {cells: 'ids', x: 'None', y: 'None'});
  });
});
