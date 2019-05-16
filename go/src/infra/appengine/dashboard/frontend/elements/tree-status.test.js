// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {TreeStatus} from './tree-status.js';
import sinon from 'sinon';
import {flush} from '@polymer/polymer/lib/utils/flush.js';

let element;
let server;
const responseHeaders = {json: {'Content-Type': 'application/json'}};

suite('tree-status', () => {
  setup(() => {
    element = document.createElement('tree-status');
    document.body.appendChild(element);
    server = sinon.fakeServer.create();
  });

  teardown(() => {
    server.restore();
  });

  test('test open', () => {
    server.respondWith(
        'GET',
        'https://infra-status.appspot.com/current?format=json', [
          200,
          responseHeaders.json,
          '{"general_state": "open", "username": "test@gmail.com", ' +
              '"message": "test open", "date": "day"}',
        ]
    );

    element._getTreeStatus();
    server.respond();

    flush(() => {
      assert.equal("test open", element._message);
      assert.equal("open", element._status);
      assert.equal(
          "Tree is open. day GMT test@gmail.com", element._statusInfo);
      assert.equal(false, element._hasError);
      done();
    });
  });

  test('test closed', () => {
    server.respondWith(
        'GET',
        'https://infra-status.appspot.com/current?format=json', [
          200,
          responseHeaders.json,
          '{"general_state": "closed", ' +
              '"message": "test closed", "date": "day"}',
        ]
    );

    element._getTreeStatus();
    server.respond();

    flush(() => {
      assert.equal("test closed", element._message);
      assert.equal("closed", element._status);
      assert.equal("Tree is closed. day GMT Unknown", element._statusInfo);
      assert.equal(false, element._hasError);
      done();
    });
  });
});
