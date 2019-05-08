// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrUpdateIssueHotlists} from './mr-update-issue-hotlists.js';

let element;
let form;

describe('mr-update-issue-hotlists', () => {
  beforeEach(async () => {
    element = document.createElement('mr-update-issue-hotlists');
    document.body.appendChild(element);

    await element.updateComplete;
    form = element.shadowRoot.querySelector('#issueHotlistsForm');
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrUpdateIssueHotlists);
  });

  it('no changes', () => {
    assert.deepEqual(element.changes, {added: [], removed: []});
  });

  it('selecting new issues produces changes', async () => {
    element.issueHotlists = [
      {name: 'Hotlist-1', ownerRef: {userId: 12345}},
      {name: 'Hotlist-2', ownerRef: {userId: 12345}},
      {name: 'Hotlist-1', ownerRef: {userId: 67890}},
    ];
    element.userHotlists = [
      {name: 'Hotlist-1', ownerRef: {userId: 67890}},
      {name: 'Hotlist-2', ownerRef: {userId: 67890}},
    ];
    element.user = {userId: 67890};

    await element.updateComplete;

    form['Hotlist-1'].checked = false;
    form['Hotlist-2'].checked = true;
    assert.deepEqual(element.changes, {
      added: [{name: 'Hotlist-2', owner: {userId: 67890}}],
      removed: [{name: 'Hotlist-1', owner: {userId: 67890}}],
    });
  });


  it('adding new issue produces changes', async () => {
    await element.updateComplete;
    form.newHotlistName.value = 'New-Hotlist';
    assert.deepEqual(element.changes, {
      added: [],
      removed: [],
      created: {
        name: 'New-Hotlist',
        summary: 'Hotlist created from issue.',
      },
    });
  });

  it('reset changes', async () => {
    element.issueHotlists = [
      {name: 'Hotlist-1', ownerRef: {userId: 12345}},
      {name: 'Hotlist-2', ownerRef: {userId: 12345}},
      {name: 'Hotlist-1', ownerRef: {userId: 67890}},
    ];
    element.userHotlists = [
      {name: 'Hotlist-1', ownerRef: {userId: 67890}},
      {name: 'Hotlist-2', ownerRef: {userId: 67890}},
    ];
    element.user = {userId: 67890};

    await element.updateComplete;

    form['Hotlist-1'].checked = false;
    form['Hotlist-2'].checked = true;
    form.newHotlisName = 'New-Hotlist';
    element.reset();
    assert.isTrue(form['Hotlist-1'].checked);
    assert.isFalse(form['Hotlist-2'].checked);
    assert.equal(form.newHotlistName.value, '');
  });
});
