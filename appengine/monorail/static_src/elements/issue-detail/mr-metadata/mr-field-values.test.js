// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrFieldValues} from './mr-field-values.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';

import {fieldTypes} from 'elements/shared/field-types.js';


let element;

suite('mr-field-values', () => {
  setup(() => {
    element = document.createElement('mr-field-values');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrFieldValues);
  });

  test('renders empty if no values', () => {
    element.values = [];

    flush();

    assert.equal('----', element.shadowRoot.textContent.trim());
  });

  test('renders user links when type is user', async () => {
    element.type = fieldTypes.USER_TYPE;
    element.values = ['test@example.com', 'hello@world.com'];

    flush();

    const links = element.shadowRoot.querySelectorAll('mr-user-link');

    await links.updateComplete;

    assert.equal(2, links.length);
    assert.include(links[0].shadowRoot.textContent, 'test@example.com');
    assert.include(links[1].shadowRoot.textContent, 'hello@world.com');
  });

  test('renders URLs when type is url', () => {
    element.type = fieldTypes.URL_TYPE;
    element.values = ['http://hello.world', 'go/link'];

    flush();

    const links = element.shadowRoot.querySelectorAll('a');

    assert.equal(2, links.length);
    assert.include(links[0].textContent, 'http://hello.world');
    assert.include(links[0].href, 'http://hello.world');
    assert.include(links[1].textContent, 'go/link');
    assert.include(links[1].href, 'go/link');
  });

  test('renders generic field when field is string', () => {
    element.type = fieldTypes.STR_TYPE;
    element.values = ['blah', 'random value', 'nothing here'];
    element.name = 'fieldName';
    element.projectName = 'project';

    flush();

    const links = element.shadowRoot.querySelectorAll('a');

    assert.equal(3, links.length);
    assert.include(links[0].textContent, 'blah');
    assert.include(links[0].href,
      '/p/project/issues/list?q=fieldName=%22blah%22');
    assert.include(links[1].textContent, 'random value');
    assert.include(links[1].href,
      '/p/project/issues/list?q=fieldName=%22random%20value%22');
    assert.include(links[2].textContent, 'nothing here');
    assert.include(links[2].href,
      '/p/project/issues/list?q=fieldName=%22nothing%20here%22');
  });
});
