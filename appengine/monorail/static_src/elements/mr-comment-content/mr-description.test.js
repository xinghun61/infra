// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrDescription} from './mr-description.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';


let element;
let commentContent;
let selectMenu;

suite('mr-description', () => {
  setup(() => {
    element = document.createElement('mr-description');
    document.body.appendChild(element);

    selectMenu = element.shadowRoot.querySelector('select');
    commentContent = element.shadowRoot.querySelector('mr-comment-content');
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrDescription);
  });

  test('changes rendered description on select change', () => {
    element.descriptionList = [
      {content: 'description one'},
      {content: 'description two'},
    ];

    flush();

    assert.equal('description two', commentContent.content);

    element.selectedIndex = 0;

    flush();

    assert.equal('description one', commentContent.content);
  });

  test('hides selector when only one description', () => {
    element.descriptionList = [
      {content: 'Hello world'},
      {content: 'rutabaga'},
    ];

    flush();

    assert.isFalse(selectMenu.hidden);

    element.descriptionList = [
      {content: 'blehh'},
    ];

    assert.isTrue(selectMenu.hidden);
  });
});
