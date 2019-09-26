// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import {prpcClient} from 'prpc-client-instance.js';
import * as project from './project.js';
import {fieldTypes, SITEWIDE_DEFAULT_COLUMNS} from 'shared/issue-fields.js';

describe('project reducers', () => {
  it('visibleMembersReducer', () => {
    assert.deepEqual(project.visibleMembersReducer({}, {
      type: project.FETCH_VISIBLE_MEMBERS_SUCCESS,
      visibleMembers: {userRefs: [{userId: '123'}]},
    }), {userRefs: [{userId: '123'}]});

    const initialState = {
      groupRefs: [{userId: '543'}],
    };

    // Overrides existing state.
    assert.deepEqual(project.visibleMembersReducer(initialState, {
      type: project.FETCH_VISIBLE_MEMBERS_SUCCESS,
      visibleMembers: {userRefs: [{userId: '123'}]},
    }), {userRefs: [{userId: '123'}]});

    // Unrelated action does not affect state.
    assert.deepEqual(project.visibleMembersReducer(initialState, {
      type: 'no-op',
      visibleMembers: {userRefs: [{userId: '123'}]},
    }), initialState);
  });
});

describe('project selectors', () => {
  it('visibleMembers', () => {
    assert.deepEqual(project.visibleMembers({}), {});
    assert.deepEqual(project.visibleMembers({project: {}}), {});
    assert.deepEqual(project.visibleMembers({project: {
      visibleMembers: {
        userRefs: [{displayName: 'test@example.com', userId: '123'}],
        groupRefs: [],
      },
    }}), {
      userRefs: [{displayName: 'test@example.com', userId: '123'}],
      groupRefs: [],
    });
  });

  it('presentationConfig', () => {
    assert.deepEqual(project.presentationConfig({}), {});
    assert.deepEqual(project.presentationConfig({project: {}}), {});
    assert.deepEqual(project.presentationConfig({project: {
      presentationConfig: {
        projectThumbnailUrl: 'test.png',
      },
    }}), {
      projectThumbnailUrl: 'test.png',
    });
  });

  it('defaultColumns', () => {
    assert.deepEqual(project.defaultColumns({}), SITEWIDE_DEFAULT_COLUMNS);
    assert.deepEqual(project.defaultColumns({project: {}}),
        SITEWIDE_DEFAULT_COLUMNS);
    assert.deepEqual(project.defaultColumns({project: {
      presentationConfig: {},
    }}), SITEWIDE_DEFAULT_COLUMNS);
    assert.deepEqual(project.defaultColumns({project: {
      presentationConfig: {defaultColSpec: 'ID+Summary+AllLabels'},
    }}), ['ID', 'Summary', 'AllLabels']);
  });

  it('currentColumns', () => {
    assert.deepEqual(project.currentColumns({}), SITEWIDE_DEFAULT_COLUMNS);
    assert.deepEqual(project.currentColumns({project: {}}),
        SITEWIDE_DEFAULT_COLUMNS);
    assert.deepEqual(project.currentColumns({project: {
      presentationConfig: {},
    }}), SITEWIDE_DEFAULT_COLUMNS);
    assert.deepEqual(project.currentColumns({project: {
      presentationConfig: {defaultColSpec: 'ID+Summary+AllLabels'},
    }}), ['ID', 'Summary', 'AllLabels']);

    // Params override default.
    assert.deepEqual(project.currentColumns({
      project: {
        presentationConfig: {defaultColSpec: 'ID+Summary+AllLabels'},
      },
      sitewide: {
        queryParams: {colspec: 'ID+Summary+ColumnName+Priority'},
      },
    }), ['ID', 'Summary', 'ColumnName', 'Priority']);
  });

  it('defaultQuery', () => {
    assert.deepEqual(project.defaultQuery({}), '');
    assert.deepEqual(project.defaultQuery({project: {}}), '');
    assert.deepEqual(project.defaultQuery({project: {
      presentationConfig: {
        defaultQuery: 'owner:me',
      },
    }}), 'owner:me');
  });

  it('currentQuery', () => {
    assert.deepEqual(project.currentQuery({}), '');
    assert.deepEqual(project.currentQuery({project: {}}), '');

    // Uses default when no params.
    assert.deepEqual(project.currentQuery({project: {
      presentationConfig: {
        defaultQuery: 'owner:me',
      },
    }}), 'owner:me');

    // Params override default.
    assert.deepEqual(project.currentQuery({
      project: {
        presentationConfig: {
          defaultQuery: 'owner:me',
        },
      },
      sitewide: {
        queryParams: {q: 'component:Infra'},
      },
    }), 'component:Infra');

    // Empty string overrides default search.
    assert.deepEqual(project.currentQuery({
      project: {
        presentationConfig: {
          defaultQuery: 'owner:me',
        },
      },
      sitewide: {
        queryParams: {q: ''},
      },
    }), '');

    // Undefined does not override default search.
    assert.deepEqual(project.currentQuery({
      project: {
        presentationConfig: {
          defaultQuery: 'owner:me',
        },
      },
      sitewide: {
        queryParams: {q: undefined},
      },
    }), 'owner:me');
  });

  it('fieldDefs', () => {
    assert.deepEqual(project.fieldDefs({project: {}}), []);
    assert.deepEqual(project.fieldDefs({project: {config: {}}}), []);
    assert.deepEqual(project.fieldDefs({
      project: {config: {fieldDefs: [{fieldRef: {fieldName: 'test'}}]}},
    }), [{fieldRef: {fieldName: 'test'}}]);
  });

  it('labelDefMap', () => {
    assert.deepEqual(project.labelDefMap({project: {}}), new Map());
    assert.deepEqual(project.labelDefMap({project: {config: {}}}), new Map());
    assert.deepEqual(project.labelDefMap({
      project: {config: {
        labelDefs: [
          {label: 'One'},
          {label: 'tWo'},
          {label: 'hello-world', docstring: 'hmmm'},
        ],
      }},
    }), new Map([
      ['one', {label: 'One'}],
      ['two', {label: 'tWo'}],
      ['hello-world', {label: 'hello-world', docstring: 'hmmm'}],
    ]));
  });

  it('labelPrefixOptions', () => {
    assert.deepEqual(project.labelPrefixOptions({project: {}}), new Map());
    assert.deepEqual(project.labelPrefixOptions({project: {config: {}}}),
        new Map());
    assert.deepEqual(project.labelPrefixOptions({
      project: {config: {
        labelDefs: [
          {label: 'One'},
          {label: 'tWo'},
          {label: 'tWo-options'},
          {label: 'hello-world', docstring: 'hmmm'},
          {label: 'hello-me', docstring: 'hmmm'},
        ],
      }},
    }), new Map([
      ['two', ['tWo', 'tWo-options']],
      ['hello', ['hello-world', 'hello-me']],
    ]));
  });

  it('labelPrefixFields', () => {
    assert.deepEqual(project.labelPrefixFields({project: {}}), []);
    assert.deepEqual(project.labelPrefixFields({project: {config: {}}}), []);
    assert.deepEqual(project.labelPrefixFields({
      project: {config: {
        labelDefs: [
          {label: 'One'},
          {label: 'tWo'},
          {label: 'tWo-options'},
          {label: 'hello-world', docstring: 'hmmm'},
          {label: 'hello-me', docstring: 'hmmm'},
        ],
      }},
    }), ['tWo', 'hello']);
  });

  it('enumFieldDefs', () => {
    assert.deepEqual(project.enumFieldDefs({project: {}}), []);
    assert.deepEqual(project.enumFieldDefs({project: {config: {}}}), []);
    assert.deepEqual(project.enumFieldDefs({
      project: {config: {fieldDefs: [
        {fieldRef: {fieldName: 'test'}},
        {fieldRef: {fieldName: 'enum', type: fieldTypes.ENUM_TYPE}},
        {fieldRef: {fieldName: 'ignore', type: fieldTypes.DATE_TYPE}},
      ]}},
    }), [{fieldRef: {fieldName: 'enum', type: fieldTypes.ENUM_TYPE}}]);
  });

  it('optionsPerEnumField', () => {
    assert.deepEqual(project.optionsPerEnumField({project: {}}), new Map());
    assert.deepEqual(project.optionsPerEnumField({
      project: {config: {
        fieldDefs: [
          {fieldRef: {fieldName: 'ignore', type: fieldTypes.DATE_TYPE}},
          {fieldRef: {fieldName: 'eNum', type: fieldTypes.ENUM_TYPE}},
        ],
        labelDefs: [
          {label: 'enum-one'},
          {label: 'ENUM-tWo'},
          {label: 'not-enum-three'},
        ],
      }},
    }), new Map([
      ['enum', [
        {label: 'enum-one', optionName: 'one'},
        {label: 'ENUM-tWo', optionName: 'tWo'},
      ]],
    ]));
  });

  it('fieldDefsByApprovalName', () => {
    assert.deepEqual(project.fieldDefsByApprovalName({project: {}}), new Map());

    assert.deepEqual(project.fieldDefsByApprovalName({project: {config: {
      fieldDefs: [
        {fieldRef: {fieldName: 'test', type: fieldTypes.INT_TYPE}},
        {fieldRef: {fieldName: 'ignoreMe', type: fieldTypes.APPROVAL_TYPE}},
        {fieldRef: {fieldName: 'yay', approvalName: 'ThisIsAnApproval'}},
        {fieldRef: {fieldName: 'ImAField', approvalName: 'ThisIsAnApproval'}},
        {fieldRef: {fieldName: 'TalkToALawyer', approvalName: 'Legal'}},
      ],
    }}}), new Map([
      ['ThisIsAnApproval', [
        {fieldRef: {fieldName: 'yay', approvalName: 'ThisIsAnApproval'}},
        {fieldRef: {fieldName: 'ImAField', approvalName: 'ThisIsAnApproval'}},
      ]],
      ['Legal', [
        {fieldRef: {fieldName: 'TalkToALawyer', approvalName: 'Legal'}},
      ]],
    ]));
  });
});

let dispatch;

describe('project action creators', () => {
  beforeEach(() => {
    sinon.stub(prpcClient, 'call');

    dispatch = sinon.stub();
  });

  afterEach(() => {
    prpcClient.call.restore();
  });

  it('fetchPresentationConfig', async () => {
    const action = project.fetchPresentationConfig('chromium');

    prpcClient.call.returns(Promise.resolve({projectThumbnailUrl: 'test'}));

    await action(dispatch);

    sinon.assert.calledWith(dispatch,
        {type: project.FETCH_PRESENTATION_CONFIG_START});

    sinon.assert.calledWith(
        prpcClient.call,
        'monorail.Projects',
        'GetPresentationConfig',
        {projectName: 'chromium'});

    sinon.assert.calledWith(dispatch, {
      type: project.FETCH_PRESENTATION_CONFIG_SUCCESS,
      presentationConfig: {projectThumbnailUrl: 'test'},
    });
  });

  it('fetchVisibleMembers', async () => {
    const action = project.fetchVisibleMembers('chromium');

    prpcClient.call.returns(Promise.resolve({userRefs: [{userId: '123'}]}));

    await action(dispatch);

    sinon.assert.calledWith(dispatch,
        {type: project.FETCH_VISIBLE_MEMBERS_START});

    sinon.assert.calledWith(
        prpcClient.call,
        'monorail.Projects',
        'GetVisibleMembers',
        {projectName: 'chromium'});

    sinon.assert.calledWith(dispatch, {
      type: project.FETCH_VISIBLE_MEMBERS_SUCCESS,
      visibleMembers: {userRefs: [{userId: '123'}]},
    });
  });
});
