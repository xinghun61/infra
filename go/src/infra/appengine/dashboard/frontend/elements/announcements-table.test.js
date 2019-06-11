// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {AnnouncementsTable} from './announcements-table.js';
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
  {
    messageContent: 'abandoned announcement.',
    creator: 'fox',
    id: '223',
    startTime: '2019-05-28T23:41:18.637847Z',
  }];

suite('announcements-table', () => {
  setup(() => {
    element = document.createElement('announcements-table');
    document.body.appendChild(element);
    prpcStub = sinon.stub(prpcClient, 'call');
  });

  teardown(function() {
    prpcStub.restore();
  });

  test('initializes', () => {
    assert.instanceOf(element, AnnouncementsTable);
  });

  test('no announcements', async () => {
    element.announcements = [];
    await element.updateComplete;
    const tableRows = element.shadowRoot.querySelector('table').rows;
    assert.equal(tableRows.length, 2);
    assert.equal(tableRows[1].innerText, 'No announcements.');
  });

  test('live announcements trooper', async () => {
    const retirePromise = Promise.resolve(
      {'retired': true, 'id': 123});
    prpcStub.returns(retirePromise);
    element.isTrooper = true;
    element.announcements = ANN;
    await element.updateComplete;
    const tableRows = element.shadowRoot.querySelector('table').rows;

    const expectedNumRows = ANN.length + 1;
    const expectedNumCells = 3 + (element.isTrooper ? 1: 0);
    assert.equal(tableRows.length, expectedNumRows);
    assert.equal(tableRows[0].cells.length, expectedNumCells);
    assert.equal(tableRows[1].cells.length, expectedNumCells);

    // Assert announcements-changed fired and RetireAnnouncement called
    const listener = sinon.spy();
    element.addEventListener('announcements-changed', listener);

    element.shadowRoot.querySelector('button').click();

    sinon.assert.calledWith(
      prpcStub, 'dashboard.ChopsAnnouncements', 'RetireAnnouncement',
      {announcementId: element.announcements[0].id});
    await retirePromise;
    sinon.assert.calledOnce(listener);
  });

  test('live announcements non-trooper', async () => {
    element.announcements = ANN;
    await element.updateComplete;
    const tableRows = element.shadowRoot.querySelector('table').rows;

    const expectedNumRows = ANN.length + 1;
    const expectedNumCells = 3 + (element.isTrooper && !element.retired ? 1: 0);
    assert.equal(tableRows.length, expectedNumRows);
    assert.equal(tableRows[0].cells.length, expectedNumCells);
    assert.equal(tableRows[1].cells.length, expectedNumCells);

    // Assert no buttons offered.
    assert.equal(element.shadowRoot.querySelector('button'), null);
  });

  test('retired announcements trooper', async () => {
    element.announcements = ANN;
    element.isTrooper = true;
    element.retired = true;
    await element.updateComplete;
    const tableRows = element.shadowRoot.querySelector('table').rows;

    const expectedNumRows = ANN.length + 1;
    const expectedNumCells = 3 + (element.isTrooper && !element.retired ? 1: 0);
    assert.equal(tableRows.length, expectedNumRows);
    assert.equal(tableRows[0].cells.length, expectedNumCells);
    assert.equal(tableRows[1].cells.length, expectedNumCells);

    // Assert no buttons offered.
    assert.equal(element.shadowRoot.querySelector('button'), null);
  });

  test('retired announcements non-trooper', async () => {
    element.announcements = ANN;
    element.retired = true;
    await element.updateComplete;
    const tableRows = element.shadowRoot.querySelector('table').rows;

    assert.isUndefined(element.isTrooper);
    const expectedNumRows = ANN.length + 1;
    const expectedNumCells = 3 + (element.isTrooper && !element.retired ? 1: 0);
    assert.equal(tableRows.length, expectedNumRows);
    assert.equal(tableRows[0].cells.length, expectedNumCells);
    assert.equal(tableRows[1].cells.length, expectedNumCells);

    // Assert no buttons offered.
    assert.equal(element.shadowRoot.querySelector('button'), null);
  });
});
