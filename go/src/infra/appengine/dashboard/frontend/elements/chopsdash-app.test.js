// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {ChopsdashApp} from './chopsdash-app.js';
import sinon from 'sinon';
import {flush} from '@polymer/polymer/lib/utils/flush.js';

let element;
let server;
let countdownStub;
const responseHeaders = {
  json: {'Content-Type': 'application/json'},
};

suite('chospdash-app', () => {
  setup(function() {
    element = document.createElement('chopsdash-app');
    document.body.appendChild(element);
    element.latestDateTs = 1500318743000; // July 17, 2017 12:12:23 PM DST
    server = sinon.fakeServer.create();
    countdownStub = sinon.stub(element, '_refreshCountdown');
  });

  teardown(function() {
    server.restore();
  });

  test('test simple', () => {
    server.respondWith(
      'POST',
      '/prpc/dashboard.ChopsServiceStatus/GetAllServicesData',
      [
        200,
        responseHeaders.json,
        ")]}'" + '{' +
            '"services":[], ' +
            '"nonslaServices":[' +
            '{"name":"Commit-Queue",' +
            '"incidents":[{' +
            '"id":"0.keug6ersqamz","startTime":"1499797156",' +
            '"endTime":"1499883556","severity":"YELLOW"}]}' +
            ']}',
      ]);
    element._refreshData();
    server.respond();

    flush(() => {
      sinon.assert.calledOnce(countdownStub);
      done();
    });
  });

  test('test no data', () => {
    server.respondWith(
      'POST',
      '/prpc/dashboard.ChopsServiceStatus/GetAllServicesData',
      [
        200,
        responseHeaders.json,
        ")]}'" + '{' +
            '"services":[], ' +
            '"nonslaServices":[]}',
      ]);
    element.$.ajax.generateRequest();
    server.respond();

    flush(() => {
      assert.equal(0, element.nonSLAServices.length);
      assert.equal(0, element.services.length);
    });
  });
});
