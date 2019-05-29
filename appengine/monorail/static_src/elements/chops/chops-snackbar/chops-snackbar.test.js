// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import {ChopsSnackbar} from './chops-snackbar.js';

let element;
let setTimeoutFn;

describe('chops-snackbar', () => {
  beforeEach(() => {
    element = document.createElement('chops-snackbar');
    document.body.appendChild(element);
    sinon.stub(window, 'setTimeout').callsFake((fn, _) => {
      setTimeoutFn = fn;
    });
  });

  afterEach(() => {
    document.body.removeChild(element);
    window.setTimeout.restore();
  });

  it('initializes', () => {
    assert.instanceOf(element, ChopsSnackbar);
  });

  it('hides after timeout', async () => {
    element.hidden = false;
    await element.updateComplete;

    setTimeoutFn();
    assert.isTrue(element.hidden);
  });

  it('hides when closed', async () => {
    element.hidden = false;
    await element.updateComplete;

    element.close();
    assert.isTrue(element.hidden);
  });
});
