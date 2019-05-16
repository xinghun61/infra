// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {ChopsdashApp} from './chopsdash-app.js';
import sinon from 'sinon';
import {flush} from '@polymer/polymer/lib/utils/flush.js';
import {prpcClient} from 'prpc.js';

let element;
let countdownStub;
let prpcStub;
const responseHeaders = {
  json: {'Content-Type': 'application/json'},
};

suite('chospdash-app', () => {
  setup(function() {
    element = document.createElement('chopsdash-app');
    document.body.appendChild(element);
    element.latestDateTs = 1500318743000; // July 17, 2017 12:12:23 PM DST
    countdownStub = sinon.stub(element, '_refreshCountdown');
    prpcStub = sinon.stub(prpcClient, 'call');
  });
  teardown(function() {
    prpcStub.restore();
  });

  test('test simple', () => {
    prpcStub.returns(
        Promise.resolve({
          'services': [],
          'nonslaServices': [{
            'name': 'Commit-Queue',
            'incidents': [{
              'id': '0.keug6ersqamz',
              'startTime':1499797156,
              'endTime':1499883556,
              'severity':"YELLOW",
            }],
          }],
        })
    );
    element._refreshData();

    flush(() => {
      sinon.assert.calledOnce(countdownStub);
      done();
    });
  });

  test('test no data', () => {
    prpcStub.returns(
        Promise.resolve({
          'services': [],
          'nonslaServices': [],
        })
    );
    element._refreshData();

    flush(() => {
      assert.equal(0, element.nonSLAServices.length);
      assert.equal(0, element.services.length);
    });
  });
});
