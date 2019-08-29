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
    const state = {
      user: {currentUser: {prefs: new Map(), prefsLoaded: false}},
      issue: {},
    };
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

  it('cue is shown if relevant message has not been dismissed', async () => {
    element.prefsLoaded = true;
    element.cuePrefName = 'code_of_conduct';

    await element.updateComplete;

    assert.isFalse(element.hidden);
    const messageEl = element.shadowRoot.querySelector('#message');
    assert.include(messageEl.innerHTML, 'chromium.googlesource.com');
  });

  it('code of conduct is specific to the project', async () => {
    element.prefsLoaded = true;
    element.cuePrefName = 'code_of_conduct';
    element.project.config.projectName = 'fuchsia';

    await element.updateComplete;

    assert.isFalse(element.hidden);
    const messageEl = element.shadowRoot.querySelector('#message');
    assert.include(messageEl.innerHTML, 'fuchsia.dev');
  });

  it('availability cue is hidden if no relevent issue particpants', () => {
    element.prefsLoaded = true;
    element.cuePrefName = 'availability_msgs';
    element.issue = {summary: 'no owners or cc'};
    assert.isTrue(element.hidden);

    element.issue = {
      summary: 'owner and ccs have no availability msg',
      ownerRef: {},
      ccRefs: [{}, {}],
    };
    assert.isTrue(element.hidden);
  });

  it('availability cue is shown if issue particpants are unavailable',
      async () => {
        element.prefsLoaded = true;
        element.cuePrefName = 'availability_msgs';
        element.referencedUsers = new Map([
          ['user@example.com', {availability: 'Never visited'}],
        ]);

        element.issue = {
          summary: 'owner is unavailable',
          ownerRef: {displayName: 'user@example.com'},
          ccRefs: [{}, {}],
        };
        await element.updateComplete;

        assert.isFalse(element.hidden);
        const messageEl = element.shadowRoot.querySelector('#message');
        assert.include(messageEl.innerText, 'Clock icons');

        element.issue = {
          summary: 'owner is unavailable',
          ownerRef: {},
          ccRefs: [
            {displayName: 'ok@example.com'},
            {displayName: 'user@example.com'}],
        };
        await element.updateComplete;
        assert.isFalse(element.hidden);
        assert.include(messageEl.innerText, 'Clock icons');
      });

  it('switch_to_parent_account cue is hidden if no linked account', () => {
    element.prefsLoaded = true;
    element.cuePrefName = 'switch_to_parent_account';

    element.user = undefined;
    assert.isTrue(element.hidden);

    element.user = {groups: []};
    assert.isTrue(element.hidden);
  });

  it('switch_to_parent_account is shown if user has parent account',
      async () => {
        element.prefsLoaded = true;
        element.cuePrefName = 'switch_to_parent_account';
        element.user = {linkedParentRef: {displayName: 'parent@example.com'}};

        await element.updateComplete;
        assert.isFalse(element.hidden);
        const messageEl = element.shadowRoot.querySelector('#message');
        assert.include(messageEl.innerText, 'a linked account');
      });

  it('search_for_numbers cue is hidden if no number was used', () => {
    element.prefsLoaded = true;
    element.cuePrefName = 'search_for_numbers';
    element.issue = {};
    element.jumpLocalId = null;
    assert.isTrue(element.hidden);
  });

  it('search_for_numbers cue is shown if jumped to issue ID',
      async () => {
        element.prefsLoaded = true;
        element.cuePrefName = 'search_for_numbers';
        element.issue = {};
        element.jumpLocalId = '123'.match(new RegExp('^\\d+$'));

        await element.updateComplete;
        assert.isFalse(element.hidden);
        const messageEl = element.shadowRoot.querySelector('#message');
        assert.include(messageEl.innerText, 'use quotes');
      });

  it('cue is dismissible unless there is attribute nondismissible',
      async () => {
        assert.isFalse(element.nondismissible);

        element.setAttribute('nondismissible', '');
        await element.updateComplete;
        assert.isTrue(element.nondismissible);
      });
});
