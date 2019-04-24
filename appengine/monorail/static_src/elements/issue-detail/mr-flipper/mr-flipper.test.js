// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import MrFlipper from './mr-flipper.js';
import sinon from 'sinon';

const xssiPrefix = ')]}\'';

let element;

suite('mr-flipper', () => {
  setup(() => {
    element = document.createElement('mr-flipper');
    document.body.appendChild(element);

    sinon.stub(window, 'fetch');

    const response = new window.Response(`${xssiPrefix}{"message": "Ok"}`, {
      status: 201,
      headers: {
        'Content-type': 'application/json',
      },
    });
    window.fetch.returns(Promise.resolve(response));
  });

  teardown(() => {
    document.body.removeChild(element);

    window.fetch.restore();
  });

  test('initializes', () => {
    assert.instanceOf(element, MrFlipper);
  });

  test('renders links', () => {
    const prevUrlEl = element.shadowRoot.querySelector('a.prev-url');
    const nextUrlEl = element.shadowRoot.querySelector('a.next-url');
    const listUrlEl = element.shadowRoot.querySelector('a.list-url');
    const countsEl = element.shadowRoot.querySelector('div.counts');

    // Test DOM after properties are updated.
    element._updateTemplate({
      cur_index: 4,
      total_count: 13,
      prev_url: 'http://prevurl/',
      next_url: 'http://nexturl/',
      list_url: 'http://listurl/',
    });
    assert.include(countsEl.innerText, '5 of 13');
    assert.equal(prevUrlEl.href, 'http://prevurl/');
    assert.equal(nextUrlEl.href, 'http://nexturl/');
    assert.equal(listUrlEl.href, 'http://listurl/');
  });
});
