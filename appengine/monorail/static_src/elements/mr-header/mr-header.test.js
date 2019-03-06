// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrHeader} from './mr-header.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';

let element;

suite('mr-header', () => {
  setup(() => {
    element = document.createElement('mr-header');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrHeader);
  });

  test('presentationConfig renders', () => {
    element.issueEntryUrl = 'https://google.com/test/';
    element.projectThumbnailUrl = 'http://images.google.com/';
    element.presentationConfig = {
      projectSummary: 'The best project',
    };

    flush();

    assert.equal(element.shadowRoot.querySelector('.project-logo').src,
      'http://images.google.com/');

    assert.equal(element.shadowRoot.querySelector('.new-issue-link').href,
      'https://google.com/test/');

    assert.equal(element.shadowRoot.querySelector('.project-selector').title,
      'The best project');
  });
});
