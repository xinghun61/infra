// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {ChopsAnnouncements} from './chops-announcements.js';
import sinon from 'sinon';
import {prpcClient} from 'prpc.js';

let element;
let prpcStub;

const ANN = [
  {
    platforms: [{name: 'gerrit'}, {name: 'monorail'}],
    messageContent: 'everything is on fire.',
    creator: 'chicken',
    id: '1234',
    startTime: '2019-05-28T23:41:18.637847Z',
  },
  {
    platforms: [{name: 'gerrit'}],
    messageContent: 'chickens need feeding.',
    creator: 'notchicken',
    id: '12345',
    startTime: '2019-05-28T23:41:18.637847Z',
  },
];

let fetchPromise;

suite('chops-announcements', () => {
  setup(() => {
    prpcStub = sinon.stub(prpcClient, 'call');
    fetchPromise = Promise.resolve({announcements: ANN});
    prpcStub.returns(fetchPromise);

    element = document.createElement('chops-announcements');
    document.body.appendChild(element);
  });

  teardown(function() {
    prpcStub.restore();
  });

  test('initializes', async () => {
    assert.instanceOf(element, ChopsAnnouncements);
  });

  test('properties passed to table', async () => {
    element.isTrooper = true;
    element.retired = false;
    await element.updateComplete;
    await fetchPromise;

    sinon.assert.calledTwice(prpcStub);
    let liveTable = element.shadowRoot.getElementById(
      'live-announcements-table');
    assert.equal(liveTable.isTrooper, true);
    assert.equal(liveTable.announcements, ANN);
    assert.equal(liveTable.retired, null);
    let retiredTable = element.shadowRoot.getElementById(
      'retired-announcements-table');
    assert.equal(retiredTable.isTrooper, true);
    assert.equal(retiredTable.announcements, ANN);
    assert.equal(retiredTable.retired, true);

    element.isTrooper = false;
    await element.updateComplete;

    liveTable = element.shadowRoot.getElementById('live-announcements-table');
    assert.equal(liveTable.isTrooper, false);
    retiredTable = element.shadowRoot.getElementById(
      'retired-announcements-table');
    assert.equal(retiredTable.isTrooper, false);
  });

  test('announcement fetched when announcements retired', async () => {
    await element.updateComplete;

    const liveTable = element.shadowRoot.getElementById(
      'live-announcements-table');
    liveTable.dispatchEvent(new CustomEvent('announcements-changed'));

    await element._fetchAnnouncements;

    sinon.assert.callCount(prpcStub, 4);
    sinon.assert.calledWith(
      prpcStub, 'dashboard.ChopsAnnouncements', 'SearchAnnouncements',
      {retired: false});
    sinon.assert.calledWith(
      prpcStub, 'dashboard.ChopsAnnouncements', 'SearchAnnouncements',
      {retired: true, offset: 0, limit: 5});
  });

  test('announcement fetched when announcement create', async () => {
    element.isTrooper = true;

    await element.updateComplete;

    const annInput = element.shadowRoot.querySelector(
      'announcement-input');
    annInput.dispatchEvent(new CustomEvent('announcement-created'));

    await element._fetchAnnoucements;

    sinon.assert.callCount(prpcStub, 4);
    sinon.assert.calledWith(
      prpcStub, 'dashboard.ChopsAnnouncements', 'SearchAnnouncements',
      {retired: false});
    sinon.assert.calledWith(
      prpcStub, 'dashboard.ChopsAnnouncements', 'SearchAnnouncements',
      {retired: true, offset: 0, limit: 5});
  });

  test('announcement-input not shown when user not trooper', async () => {
    await element.updateComplete;

    assert.isUndefined(element.isTrooper);
    const annInput = element.shadowRoot.querySelector('announcement-input');
    assert.isNull(annInput);
  });

  test('error messages empty after successful requests', async () => {
    await element.updateComplete;

    element._retiredErrorMessage = 'error fetching retired announcements';
    element._liveErrorMessage = 'error fetching live announcements';
    await element._fetchAnnouncements();

    assert.equal(element._retiredErrorMessage, '');
    assert.equal(element._liveErrorMessage, '');
  });

});
