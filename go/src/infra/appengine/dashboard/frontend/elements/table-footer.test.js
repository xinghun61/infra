// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {TableFooter} from './table-footer.js';
import sinon from 'sinon';
import {flush} from '@polymer/polymer/lib/utils/flush.js';

let element;
const baseDate = 1498028399000 // Tuesday, June 20, 2017 11:59:59 PM GMT-07:00

suite('table-footer', () => {
  setup(() => {
    element = document.createElement('table-footer');
    document.body.appendChild(element);
    element.latestDate = baseDate;
  });

  test('test enabled', () => {
    element.latestDate = baseDate;
    flush(() => {
      assert.equal(element.tsPrev, 1497423599000,
		   `found: prev = ${new Date(element.tsPrev)}`);
      assert.equal(element.tsNext, 1498633199000,
		   `found: next = ${new Date(element.tsNext)}`);
      done();
    });
  });

  test('test tap previous page', () => {
    element.latestDate = baseDate;
    flush(() => {
      element._goToPrevPage();
      assert.equal(element.latestDate, 1497423599000,
		   `found: latest = ${new Date(element.latestDate)}`);
      assert.equal(element.tsNext, 1498028399000,
		   `found: next = ${new Date(element.tsNext)}`);
      assert.equal(element.tsPrev, 1496818799000,
		   `found: prev = ${new Date(element.tsPrev)}`);
      done();
    });
  });

  test('test tap next page', () => {
    element.latestDate = baseDate;
    flush(() => {
      element._goToNextPage();
      assert.equal(element.latestDate, 1498633199000,
		   `found: latest = ${new Date(element.latestDate)}`);
      assert.equal(element.tsNext, 1499237999000,
		   `found: next = ${new Date(element.tsNext)}`);
      assert.equal(element.tsPrev, 1498028399000,
		   `found: prev = ${new Date(element.tsPrev)}`);
      done();
    });
  });

  test('test prev disabled', () => {
    // Tuesday, May 22, 2017 11:59:59 PM GMT-07:00
    let today = new Date(1495522799000);
    element.latestDate = today.getTime();
    flush(() => {
      assert.isNotOk(element.tsPrev,
		     `there should be no prev, found: ${element.tsPrev}`);
      let wantNext = new Date(today);
      wantNext.setDate(today.getDate() + 7);
      wantNext.setHours(23, 59, 59, 0);
      assert.equal(element.tsNext, wantNext.getTime(),
		   `found: next = ${new Date(element.tsNext)}`);
      done();
    });
  });

  test('test next disabled', () => {
    let today = new Date();
    element.latestDate = today.getTime();
    flush(() => {
      assert.isNotOk(element.tsNext,
		     'there should be no next, found: ${element.tsNext}');
      let wantPrev = new Date(today);
      wantPrev.setDate(today.getDate() - 7);
      wantPrev.setHours(23, 59, 59, 0);
      assert.equal(element.tsPrev, wantPrev.getTime(),
		   `found: prev = ${new Date(element.tsPrev)}`);
      done();
    });
  });
});
