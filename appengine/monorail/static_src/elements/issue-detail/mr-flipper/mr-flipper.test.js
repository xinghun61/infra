// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import MrFlipper from './mr-flipper.js';
import sinon from 'sinon';

const xssiPrefix = ')]}\'';

let element;

describe('mr-flipper', () => {
  beforeEach(() => {
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

  afterEach(() => {
    document.body.removeChild(element);

    window.fetch.restore();
  });

  it('initializes', () => {
    assert.instanceOf(element, MrFlipper);
  });

  it('renders links', async () => {
    // Test DOM after properties are updated.
    element._populateResponseData({
      cur_index: 4,
      total_count: 13,
      prev_url: 'http://prevurl/',
      next_url: 'http://nexturl/',
      list_url: 'http://listurl/',
    });

    await element.updateComplete;

    const prevUrlEl = element.shadowRoot.querySelector('a.prev-url');
    const nextUrlEl = element.shadowRoot.querySelector('a.next-url');
    const listUrlEl = element.shadowRoot.querySelector('a.list-url');
    const countsEl = element.shadowRoot.querySelector('div.counts');

    assert.equal(prevUrlEl.href, 'http://prevurl/');
    assert.equal(nextUrlEl.href, 'http://nexturl/');
    assert.equal(listUrlEl.href, 'http://listurl/');
    assert.include(countsEl.innerText, '5 of 13');
  });

  it('fetches flipper data when queryParams change', async () => {
    await element.updateComplete;

    sinon.stub(element, 'fetchFlipperData');

    element.queryParams = {id: 21, q: 'owner:me'};

    sinon.assert.notCalled(element.fetchFlipperData);

    await element.updateComplete;

    sinon.assert.calledWith(element.fetchFlipperData, 'id=21&q=owner%3Ame');
  });
});
