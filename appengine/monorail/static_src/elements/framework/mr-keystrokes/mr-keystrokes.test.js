// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrKeystrokes} from './mr-keystrokes.js';
import page from 'page';
import Mousetrap from 'mousetrap';

let element;

describe('mr-keystrokes', () => {
  beforeEach(() => {
    element = document.createElement('mr-keystrokes');
    document.body.appendChild(element);

    element.projectName = 'proj';
    element.issueId = 11;

    sinon.stub(page, 'call');
  });

  afterEach(() => {
    document.body.removeChild(element);

    page.call.restore();
  });

  it('initializes', () => {
    assert.instanceOf(element, MrKeystrokes);
  });

  it('? and esc open and close dialog', async () => {
    await element.updateComplete;
    assert.isFalse(element.opened);

    Mousetrap.trigger('?');

    await element.updateComplete;
    assert.isTrue(element.opened);

    Mousetrap.trigger('esc');

    await element.updateComplete;
    assert.isFalse(element.opened);
  });

  // TODO(zhangtiff): Figure out how to best test page navigation.
});
