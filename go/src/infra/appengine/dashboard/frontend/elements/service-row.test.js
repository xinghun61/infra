// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {ServiceRow} from './service-row.js';
import sinon from 'sinon';
import {flush} from '@polymer/polymer/lib/utils/flush.js';

let element;
let lastDate;

suite('service-row', function() {
  setup(() => {
    element = document.createElement('service-row');
    document.body.appendChild(element);
    lastDate = new Date(1498114800000); // 22/06/2017 PTZ

    for (let i = 6; i >= 0; i--) {
      let date = new Date(lastDate);
      date.setDate(lastDate.getDate() - i);
      element.dates.push(date);
    }
    element.incidents = [
      {
        severity: 'RED',
        start_time: '1496693923',
        end_time: '1497788570',
      },{
        severity: 'YELLOW',
        start_time: '1497293923',
        end_time: '1497789570',
      },{
        severity: 'YELLOW',
        start_time: '1497793923',
        end_time: '1497783570',
      },
    ];
  });

  test('test properties are passed', () => {
    flush(() => {
      let row = element.shadowRoot.querySelector('span');
      assert.equal(row.querySelectorAll('incident-icon').length, 3);
      row.querySelectorAll(
          'incident-icon').forEach((incidentIcon, index) => {
            assert.equal(incidentIcon.incident, element.incidents[index]);
            assert.equal(incidentIcon.dates, element.dates);
          });
      done();
    });
  });
});
