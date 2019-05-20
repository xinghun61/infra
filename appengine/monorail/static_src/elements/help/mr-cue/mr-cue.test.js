// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrCue} from './mr-cue.js';
import page from 'page';

let element;

describe('mr-cue', () => {
  beforeEach(() => {
    element = document.createElement('mr-cue');
    document.body.appendChild(element);

    sinon.stub(page, 'call');
  });

  afterEach(() => {
    document.body.removeChild(element);

    page.call.restore();
  });

  it('initializes', () => {
    assert.instanceOf(element, MrCue);
  });

  it('stateChanged', () => {
    const state = {user: {currentUser:
      {prefs: new Map(), prefsLoaded: false}}};
    element.stateChanged(state);
    assert.deepEqual(element.prefs, new Map());
    assert.isFalse(element.prefsLoaded);
  });

  it('cues are hidden before prefs load', () => {
    element.prefsLoaded = false;
    assert.isTrue(element.hidden);
  });

  it('cue is hidden if user already dismissed it', () => {
    element.prefsLoaded = true;
    element.cuePrefName = 'code_of_conduct';
    element.prefs = new Map([['code_of_conduct', 'true']]);
    assert.isTrue(element.hidden);
  });

  it('cue is hidden if no relevent message', () => {
    element.prefsLoaded = true;
    element.cuePrefName = 'this_has_no_message';
    assert.isTrue(element.hidden);
  });

  it('cue is shown if relevent message has not been dismissed', () => {
    element.prefsLoaded = true;
    element.cuePrefName = 'code_of_conduct';
    assert.isFalse(element.hidden);
  });
});
