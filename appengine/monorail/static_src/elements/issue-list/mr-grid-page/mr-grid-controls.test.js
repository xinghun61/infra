// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import sinon from 'sinon';
import {assert} from 'chai';
import {MrGridControls} from './mr-grid-controls';

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

    const event = document.createEvent('Event');
    event.initEvent('change');

    dropdownRows.selection = 'Status';
    dropdownRows.dispatchEvent(event);
    sinon.assert.calledWith(stub, sinon.match({y: 'Status'}));

    dropdownCols.selection = 'Blocking';
    dropdownCols.dispatchEvent(event);
    sinon.assert.calledWith(stub, sinon.match({x: 'Blocking', y: 'Status'}));
  });

  it('button selection creates url params', async () => {
    await element.updateComplete;

    const cellsToggle = element.shadowRoot.querySelector('.cells');

    const stub = sinon.stub(element, '_changeUrlParams');

    const event = document.createEvent('Event');
    event.initEvent('change');

    cellsToggle.value = 'ids';
    cellsToggle.dispatchEvent(event);
    sinon.assert.calledWith(stub, sinon.match(
        {cells: 'ids', x: 'None', y: 'None'}));
  });
});
