// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrFieldValues} from './mr-field-values.js';

import {fieldTypes} from 'elements/shared/issue-fields.js';


let element;

describe('mr-field-values', () => {
  beforeEach(() => {
    element = document.createElement('mr-field-values');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrFieldValues);
  });

  it('renders empty if no values', async () => {
    element.values = [];

    await element.updateComplete;

    assert.equal('----', element.shadowRoot.textContent.trim());
  });

  it('renders user links when type is user', async () => {
    element.type = fieldTypes.USER_TYPE;
    element.values = ['test@example.com', 'hello@world.com'];

    await element.updateComplete;

    const links = element.shadowRoot.querySelectorAll('mr-user-link');

    await links.updateComplete;

    assert.equal(2, links.length);
    assert.include(links[0].shadowRoot.textContent, 'test@example.com');
    assert.include(links[1].shadowRoot.textContent, 'hello@world.com');
  });

  it('renders URLs when type is url', async () => {
    element.type = fieldTypes.URL_TYPE;
    element.values = ['http://hello.world', 'go/link'];

    await element.updateComplete;

    const links = element.shadowRoot.querySelectorAll('a');

    assert.equal(2, links.length);
    assert.include(links[0].textContent, 'http://hello.world');
    assert.include(links[0].href, 'http://hello.world');
    assert.include(links[1].textContent, 'go/link');
    assert.include(links[1].href, 'go/link');
  });

  it('renders generic field when field is string', async () => {
    element.type = fieldTypes.STR_TYPE;
    element.values = ['blah', 'random value', 'nothing here'];
    element.name = 'fieldName';
    element.projectName = 'project';

    await element.updateComplete;

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
