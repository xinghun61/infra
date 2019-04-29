// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {CurrentIncidentIcon} from './current-incident-icon.js';
import sinon from 'sinon';
import {flush} from '@polymer/polymer/lib/utils/flush.js';


let element;
let incidentY;
let incidentYC;
let incidentR;
let incidentRC;

suite('current-incident-icon', () => {
  setup(() => {
    element = document.createElement('currend-incident-icon');
    document.body.appendChild(element);
    incidentY = {
      severity: 'YELLOW',
      open: 'true',
      incidentLink: 'https://www.google.com',
    };
    incidentYC = {severity: 'YELLOW'};
    incidentR = {
      severity: 'RED',
      open: 'true',
      incidentLink: 'https://www.google.com',
    };
    incidentRC = {severity: 'RED'};
  });

  test('_icon', () => {
      flush(() => {
        element.incidents = [incidentY, incidentYC, incidentR, incidentRC];
        assert.deepEqual(element._icon, incidentR);

        element.incidents = [incidentY, incidentYC, incidentRC];
        assert.deepEqual(element._icon, incidentY);

        element.incidents = [incidentYC, incidentRC];
        assert.deepEqual(element._icon, {severity: 'GREEN', incidentLink: ''});

        done();
      });
  });

  test('click enabled', () => {
    element.isGoogler = true;
    element.incidents = [incidentY, incidentYC, incidentR, incidentRC];
    flush(() => {
      assert.isTrue(element.$.jsCurrentIncident.classList.contains('clickable'));
      done();
    });
  });

  test('click disabled', () => {
    element.isGoogler = true;
    element.incidents = [incidentYC, incidentRC];
    flush(function() {
      assert.isFalse(element.$.jsCurrentIncident.classList.contains('clickable'));
      done();
    });
  });
});
