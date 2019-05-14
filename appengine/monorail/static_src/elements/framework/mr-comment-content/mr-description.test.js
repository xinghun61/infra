// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrDescription} from './mr-description.js';


let element;

describe('mr-description', () => {
  beforeEach(() => {
    element = document.createElement('mr-description');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrDescription);
  });

  it('changes rendered description on select change', async () => {
    element.descriptionList = [
      {content: 'description one', commenter: {displayName: 'name'}},
      {content: 'description two', commenter: {displayName: 'name'}},
    ];

    await element.updateComplete;
    await element.updateComplete;

    const commentContent =
      element.shadowRoot.querySelector('mr-comment-content');
    assert.equal('description two', commentContent.content);

    element.selectedIndex = 0;

    await element.updateComplete;

    assert.equal('description one', commentContent.content);
  });

  it('hides selector when only one description', async () => {
    element.descriptionList = [
      {content: 'Hello world', commenter: {displayName: 'name'}},
      {content: 'rutabaga', commenter: {displayName: 'name'}},
    ];

    await element.updateComplete;

    const selectMenu = element.shadowRoot.querySelector('select');
    assert.isFalse(selectMenu.hidden);

    element.descriptionList = [
      {content: 'blehh', commenter: {displayName: 'name'}},
    ];

    await element.updateComplete;

    assert.isTrue(selectMenu.hidden);
  });
});
