// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {StatusTable} from './status-table.js';
import sinon from 'sinon';
import {flush} from '@polymer/polymer/lib/utils/flush.js';

let element;
const baseDateTs = 1498114800000; // 22/06/2017 PTZ

suite('status-table', function() {
  setup(function(){
    element = document.createElement('status-table');
    document.body.appendChild(element);
    element.latestDateTs = baseDateTs;

    let service = {name: 'Monorail'}
    service.incidents = [
      {
        severity: 'RED',
        startTime: '1497693923',
        endTime: '1497787570',
      },{
        severity: 'YELLOW',
        startTime: '1497693723',
        endTime: '1497787520',
      },{
        severity: 'YELLOW',
        startTime: '1497693723',
        endTime: '1497787590',
      },
    ];

    let serviceTwo = {name: 'Sheriff-O-Matic'}
    serviceTwo.incidents = [
      {
        severity: 'YELLOW',
        startTime: '1497653923',
        endTime: '1497799570',
      },{
        severity: 'RED',
        startTime: '1497773923',
        endTime: '1497787570',
      },
    ];

    let serviceThree = {name: 'Code Search'}
    serviceThree.incidents = [
      {
        severity: 'YELLOW',
        startTime: '1497653923',
        endTime: '1497799570',
      },{
        severity: 'YELLOW',
        startTime: '1497773923',
        open: 'true',
      },
    ];

    element.push('services', service, serviceTwo, serviceThree);

    });

  test('test elements created', () => {
    flush(() => {
      let prettyDates = [
        "2017-6-16", "2017-6-17", "2017-6-18",
        "2017-6-19", "2017-6-20", "2017-6-21", "2017-6-22"
      ]
      element.formattedDates.forEach((prettyDate, i) => {
        assert.equal(prettyDate, prettyDates[i]);
      });
      element.dates.reverse().forEach((date, i) => {
        let ts = new Date(baseDateTs);
        assert.equal(ts.setDate(ts.getDate() -i), date.getTime());
      });
      done();
    });
  });

});
