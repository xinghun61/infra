// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import {MrShowColumnsDropdown} from './mr-show-columns-dropdown.js';


let element;

describe('mr-show-columns-dropdown', () => {
  beforeEach(() => {
    element = document.createElement('mr-show-columns-dropdown');
    document.body.appendChild(element);

    sinon.stub(element, '_baseUrl').returns('/p/chromium/issues/list');
    sinon.stub(element, '_page');
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrShowColumnsDropdown);
  });

  it('clicking unset column in show columns menu adds new column', async () => {
    element.defaultIssueFields = ['ID'];
    element.columns = [];

    sinon.stub(element, 'addColumn');

    await element.updateComplete;

    element.clickItem(0);

    sinon.assert.calledWith(element.addColumn, 'ID');
  });

  it('clicking set column in show columns menu removes column', async () => {
    element.defaultIssueFields = ['ID'];
    element.columns = ['ID'];

    sinon.stub(element, 'removeColumn');

    await element.updateComplete;

    element.clickItem(0);

    sinon.assert.calledWith(element.removeColumn, 0);
  });

  it('sorts default column options', async () => {
    element.defaultIssueFields = ['ID', 'Summary', 'AllLabels'];
    element.columns = [];

    // Re-compute menu items on update.
    await element.updateComplete;
    const options = element.items;

    assert.equal(options.length, 3);

    assert.equal(options[0].text.trim(), 'AllLabels');
    assert.equal(options[0].icon, '');

    assert.equal(options[1].text.trim(), 'ID');
    assert.equal(options[1].icon, '');

    assert.equal(options[2].text.trim(), 'Summary');
    assert.equal(options[2].icon, '');
  });

  it('sorts selected columns above unselected columns', async () => {
    element.defaultIssueFields = ['ID', 'Summary', 'AllLabels'];
    element.columns = ['ID'];

    // Re-compute menu items on update.
    await element.updateComplete;
    const options = element.items;

    assert.equal(options.length, 3);

    assert.equal(options[0].text.trim(), 'ID');
    assert.equal(options[0].icon, 'check');

    assert.equal(options[1].text.trim(), 'AllLabels');
    assert.equal(options[1].icon, '');

    assert.equal(options[2].text.trim(), 'Summary');
    assert.equal(options[2].icon, '');
  });

  it('sorts field defs and label prefix column options', async () => {
    element.defaultIssueFields = ['ID', 'Summary'];
    element.columns = [];
    element._fieldDefs = [
      {fieldRef: {fieldName: 'HelloWorld'}},
      {fieldRef: {fieldName: 'TestField'}},
    ];

    element._labelPrefixFields = ['Milestone', 'Priority'];

    // Re-compute menu items on update.
    await element.updateComplete;
    const options = element.items;

    assert.equal(options.length, 6);
    assert.equal(options[0].text.trim(), 'HelloWorld');
    assert.equal(options[0].icon, '');

    assert.equal(options[1].text.trim(), 'ID');
    assert.equal(options[1].icon, '');

    assert.equal(options[2].text.trim(), 'Milestone');
    assert.equal(options[2].icon, '');

    assert.equal(options[3].text.trim(), 'Priority');
    assert.equal(options[3].icon, '');

    assert.equal(options[4].text.trim(), 'Summary');
    assert.equal(options[4].icon, '');

    assert.equal(options[5].text.trim(), 'TestField');
    assert.equal(options[5].icon, '');
  });

  it('add approver fields for approval type fields', async () => {
    element.defaultIssueFields = [];
    element.columns = [];
    element._fieldDefs = [
      {fieldRef: {fieldName: 'HelloWorld', type: 'APPROVAL_TYPE'}},
    ];

    // Re-compute menu items on update.
    await element.updateComplete;
    const options = element.items;

    assert.equal(options.length, 2);
    assert.equal(options[0].text.trim(), 'HelloWorld');
    assert.equal(options[0].icon, '');

    assert.equal(options[1].text.trim(), 'HelloWorld-Approver');
    assert.equal(options[1].icon, '');
  });

  it('reloadColspec navigates to page with new colspec', () => {
    element.columns = ['ID', 'Summary'];
    element.queryParams = {};

    element.reloadColspec(['Summary', 'AllLabels']);

    sinon.assert.calledWith(element._page,
        '/p/chromium/issues/list?colspec=Summary%20AllLabels');
  });

  it('addColumn adds a column', () => {
    element.columns = ['ID', 'Summary'];

    sinon.stub(element, 'reloadColspec');

    element.addColumn('AllLabels');

    sinon.assert.calledWith(element.reloadColspec,
        ['ID', 'Summary', 'AllLabels']);
  });

  it('removeColumn removes a column', () => {
    element.columns = ['ID', 'Summary'];

    sinon.stub(element, 'reloadColspec');

    element.removeColumn(0);

    sinon.assert.calledWith(element.reloadColspec, ['Summary']);
  });
});
