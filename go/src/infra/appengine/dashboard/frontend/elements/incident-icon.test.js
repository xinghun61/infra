// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// These tests were written in the PTZ.
// These may fail if run in a different time zone.

import {assert} from 'chai';
import {IncidentIcon} from './incident-icon.js';
import sinon from 'sinon';
import {flush} from '@polymer/polymer/lib/utils/flush.js';

let element;
let lastDate;

suite('incident-icon', function() {
  setup(() => {
    element = document.createElement('incident-icon');
    document.body.appendChild(element);
    element.dates = [];
    lastDate = new Date(1498114800000); // 22/06/2017 PTZ
    for (let i = 6; i >= 0; i--) {
      let date = new Date(lastDate);
      date.setDate(lastDate.getDate() - i);
      element.dates.push(date);
    }
  });

  test('incident within time range', () => {
    element.incident = {
      severity: 'RED',
      startTime: '1497693923', // 17/06/2017 3:05:23 PTZ
      endTime: '1497787570', // 18/06/2017 5:6:10 PTZ
    };

    flush(() => {
      assert.equal(element._computeColor(element.incident), 'red');
      assert.isTrue(
          element.$.jsLeft.classList.value.includes('left red'),
          'left color');
      assert.isTrue(
          element.$.jsRight.classList.value.includes('right red'),
          'right color');
      assert.equal(
      	  element.style.getPropertyValue('--incident-z-index'), '2',
          'check z-index for red incident');
      done();
    });
  });

  test('incident exceeds dashboard range', () => {
    element.incident = {
      severity: 'YELLOW',
      startTime: '1497573492', // 15/06/2017 17:38:12 PTZ
      endTime: '1498264692', // 23/06/2017 17:38:12 PTZ
    };
    flush(() => {
      assert.equal(element._computeColor(element.incident), 'yellow');
      assert.isTrue(
          element.$.jsLeft.classList.value.includes('hidden'),
          'left classes');
      assert.isTrue(
          element.$.jsRight.classList.value.includes('hidden'),
          'right classes');
      assert.equal(
          element.style.getPropertyValue('--incident-width'), '100%',
          'check width');
      assert.equal(
          element.style.getPropertyValue('--incident-left'), '0%',
          'check left');
      assert.equal(
          element.style.getPropertyValue('--incident-z-index'), '1',
          'check z-index for yellow incident');
      done();
    });
  });
});
