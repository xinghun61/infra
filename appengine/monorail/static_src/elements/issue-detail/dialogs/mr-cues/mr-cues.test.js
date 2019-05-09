// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrCues} from './mr-cues.js';
import page from 'page';

let element;

describe('mr-cues', () => {
  beforeEach(() => {
    element = document.createElement('mr-cues');
    document.body.appendChild(element);

    sinon.stub(page, 'call');
  });

  afterEach(() => {
    document.body.removeChild(element);

    page.call.restore();
  });

  it('initializes', () => {
    assert.instanceOf(element, MrCues);
  });

  it('stateChanged', () => {
    const state = {user: {currentUser:
      {prefs: new Map(), prefsLoaded: false}}};
    element.stateChanged(state);
    assert.deepEqual(element.prefs, new Map());
    assert.isFalse(element.prefsLoaded);
  });

  it('anon does not see privacy dialog', () => {
    assert.isFalse(element._showPrivacyDialog);
  });

  it('signed in user sees no privacy dialog before prefs load', () => {
    element.userDisplayName = 'user@example.com';
    element.prefsLoaded = false;
    assert.isFalse(element._showPrivacyDialog);
  });

  it('signed in user sees no privacy dialog if dismissal pref set', () => {
    element.userDisplayName = 'user@example.com';
    element.prefsLoaded = true;
    element.prefs = new Map([['privacy_click_through', 'true']]);
    assert.isFalse(element._showPrivacyDialog);
  });

  it('signed in user sees privacy dialog if dismissal pref missing', () => {
    element.userDisplayName = 'user@example.com';
    element.prefsLoaded = true;
    element.prefs = new Map();
    assert.isTrue(element._showPrivacyDialog);
  });

  it('anon does not see corp mode dialog', () => {
    assert.isFalse(element._showCorpModeDialog);
  });

  it('signed in user sees no corp mode dialog before prefs load', () => {
    element.userDisplayName = 'user@example.com';
    element.prefsLoaded = false;
    assert.isFalse(element._showCorpModeDialog);
  });

  it('signed in user sees no corp mode dialog if dismissal pref set', () => {
    element.userDisplayName = 'user@example.com';
    element.prefsLoaded = true;
    element.prefs = new Map([['corp_mode_click_through', 'true']]);
    assert.isFalse(element._showCorpModeDialog);
  });

  it('non-corp user sees no corp mode dialog', () => {
    element.userDisplayName = 'user@example.com';
    element.prefsLoaded = true;
    element.prefs = new Map();
    assert.isFalse(element._showCorpModeDialog);
  });

  it('corp user sees corp mode dialog if dismissal pref missing', () => {
    element.userDisplayName = 'user@example.com';
    element.prefsLoaded = true;
    element.prefs = new Map([['public_issue_notice', 'true']]);
    assert.isTrue(element._showCorpModeDialog);
  });

  it('corp user sees no corp mode dialog in members-only project', () => {
    window.CS_env = {projectIsRestricted: true};
    element.userDisplayName = 'user@example.com';
    element.prefsLoaded = true;
    element.prefs = new Map([['public_issue_notice', 'true']]);
    assert.isFalse(element._showCorpModeDialog);
  });
});
