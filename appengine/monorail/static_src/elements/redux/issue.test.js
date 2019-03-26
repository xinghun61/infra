// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import * as issue from './issue.js';
import {fieldTypes} from '../shared/field-types.js';

suite('issue', () => {
  test('issue', () => {
    assert.isUndefined(issue.issue({}));
    assert.deepEqual(issue.issue({issue: {localId: 100}}),
      {localId: 100});
  });

  test('fieldValues', () => {
    assert.isUndefined(issue.fieldValues({}));
    assert.isUndefined(issue.fieldValues({issue: {}}));
    assert.deepEqual(issue.fieldValues({
      issue: {fieldValues: [{value: 'v'}]},
    }), [{value: 'v'}]);
  });

  test('type', () => {
    assert.isUndefined(issue.type({}));
    assert.isUndefined(issue.type({issue: {}}));
    assert.isUndefined(issue.type({
      issue: {fieldValues: [{value: 'v'}]},
    }));
    assert.deepEqual(issue.type({
      issue: {fieldValues: [
        {fieldRef: {fieldName: 'IgnoreMe'}, value: 'v'},
        {fieldRef: {fieldName: 'Type'}, value: 'Defect'},
      ]},
    }), 'Defect');
  });

  test('restrictions', () => {
    assert.deepEqual(issue.restrictions({}), {});
    assert.deepEqual(issue.restrictions(
      {issue: {}}), {});
    assert.deepEqual(issue.restrictions(
      {issue: {labelRefs: []}}), {});

    assert.deepEqual(issue.restrictions({issue: {labelRefs: [
      {label: 'IgnoreThis'},
      {label: 'IgnoreThis2'},
    ]}}), {});

    assert.deepEqual(issue.restrictions({issue: {labelRefs: [
      {label: 'IgnoreThis'},
      {label: 'IgnoreThis2'},
      {label: 'Restrict-View-Google'},
      {label: 'Restrict-EditIssue-hello'},
      {label: 'Restrict-EditIssue-test'},
      {label: 'Restrict-AddIssueComment-HELLO'},
    ]}}), {
      'view': ['Google'],
      'edit': ['hello', 'test'],
      'comment': ['HELLO'],
    });
  });

  test('isRestricted', () => {
    assert.isFalse(issue.isRestricted({}));
    assert.isFalse(issue.isRestricted({}));
    assert.isFalse(issue.isRestricted({issue: {}}));
    assert.isFalse(issue.isRestricted({issue: {labelRefs: []}}));

    assert.isTrue(issue.isRestricted({issue: {labelRefs: [
      {label: 'IgnoreThis'},
      {label: 'IgnoreThis2'},
      {label: 'Restrict-View-Google'},
    ]}}));

    assert.isFalse(issue.isRestricted({issue: {labelRefs: [
      {label: 'IgnoreThis'},
      {label: 'IgnoreThis2'},
      {label: 'Restrict-View'},
      {label: 'Restrict'},
      {label: 'RestrictView'},
      {label: 'Restt-View'},
    ]}}));

    assert.isTrue(issue.isRestricted({issue: {labelRefs: [
      {label: 'restrict-view-google'},
    ]}}));

    assert.isTrue(issue.isRestricted({issue: {labelRefs: [
      {label: 'restrict-EditIssue-world'},
    ]}}));

    assert.isTrue(issue.isRestricted({issue: {labelRefs: [
      {label: 'RESTRICT-ADDISSUECOMMENT-everyone'},
    ]}}));
  });

  test('isOpen', () => {
    assert.isFalse(issue.isOpen({}));
    assert.isTrue(issue.isOpen({issue: {statusRef: {meansOpen: true}}}));
    assert.isFalse(issue.isOpen({issue: {statusRef: {meansOpen: false}}}));
  });

  test('blockingIssues', () => {
    const relatedIssues = new Map([
      ['proj:1',
        {localId: 1, projectName: 'proj', labelRefs: [{label: 'label'}]}],
      ['proj:3',
        {localId: 3, projectName: 'proj', labelRefs: []}],
      ['chromium:332',
        {localId: 332, projectName: 'chromium', labelRefs: []}],
    ]);
    const stateNoReferences = {
      issue: {
        blockingIssueRefs: [{localId: 1, projectName: 'proj'}],
      },
      relatedIssues: new Map(),
    };
    assert.deepEqual(issue.blockingIssues(stateNoReferences),
      [{localId: 1, projectName: 'proj'}]
    );

    const stateNoIssues = {
      issue: {
        blockingIssueRefs: [],
      },
      relatedIssues: relatedIssues,
    };
    assert.deepEqual(issue.blockingIssues(stateNoIssues), []);

    const stateIssuesWithReferences = {
      issue: {
        blockingIssueRefs: [
          {localId: 1, projectName: 'proj'},
          {localId: 332, projectName: 'chromium'},
        ],
      },
      relatedIssues: relatedIssues,
    };
    assert.deepEqual(issue.blockingIssues(stateIssuesWithReferences),
      [
        {localId: 1, projectName: 'proj', labelRefs: [{label: 'label'}]},
        {localId: 332, projectName: 'chromium', labelRefs: []},
      ]);
  });

  test('blockedOnIssues', () => {
    const relatedIssues = new Map([
      ['proj:1',
        {localId: 1, projectName: 'proj', labelRefs: [{label: 'label'}]}],
      ['proj:3',
        {localId: 3, projectName: 'proj', labelRefs: []}],
      ['chromium:332',
        {localId: 332, projectName: 'chromium', labelRefs: []}],
    ]);
    const stateNoReferences = {
      issue: {
        blockedOnIssueRefs: [{localId: 1, projectName: 'proj'}],
      },
      relatedIssues: new Map(),
    };
    assert.deepEqual(issue.blockedOnIssues(stateNoReferences),
      [{localId: 1, projectName: 'proj'}]
    );

    const stateNoIssues = {
      issue: {
        blockedOnIssueRefs: [],
      },
      relatedIssues: relatedIssues,
    };
    assert.deepEqual(issue.blockedOnIssues(stateNoIssues), []);

    const stateIssuesWithReferences = {
      issue: {
        blockedOnIssueRefs: [
          {localId: 1, projectName: 'proj'},
          {localId: 332, projectName: 'chromium'},
        ],
      },
      relatedIssues: relatedIssues,
    };
    assert.deepEqual(issue.blockedOnIssues(stateIssuesWithReferences),
      [
        {localId: 1, projectName: 'proj', labelRefs: [{label: 'label'}]},
        {localId: 332, projectName: 'chromium', labelRefs: []},
      ]);
  });

  test('sortedBlockedOn', () => {
    const relatedIssues = new Map([
      ['proj:1',
        {localId: 1, projectName: 'proj', statusRef: {meansOpen: true}}],
      ['proj:3',
        {localId: 3, projectName: 'proj', statusRef: {meansOpen: false}}],
      ['proj:4',
        {localId: 4, projectName: 'proj', statusRef: {meansOpen: false}}],
      ['proj:5',
        {localId: 5, projectName: 'proj', statusRef: {meansOpen: false}}],
      ['chromium:332',
        {localId: 332, projectName: 'chromium', statusRef: {meansOpen: true}}],
    ]);
    const stateNoReferences = {
      issue: {
        blockedOnIssueRefs: [
          {localId: 3, projectName: 'proj'},
          {localId: 1, projectName: 'proj'},
        ],
      },
      relatedIssues: new Map(),
    };
    assert.deepEqual(issue.sortedBlockedOn(stateNoReferences), [
      {localId: 3, projectName: 'proj'},
      {localId: 1, projectName: 'proj'},
    ]);
    const stateReferences = {
      issue: {
        blockedOnIssueRefs: [
          {localId: 3, projectName: 'proj'},
          {localId: 1, projectName: 'proj'},
        ],
      },
      relatedIssues: relatedIssues,
    };
    assert.deepEqual(issue.sortedBlockedOn(stateReferences), [
      {localId: 1, projectName: 'proj', statusRef: {meansOpen: true}},
      {localId: 3, projectName: 'proj', statusRef: {meansOpen: false}},
    ]);
    const statePreservesArrayOrder = {
      issue: {
        blockedOnIssueRefs: [
          {localId: 5, projectName: 'proj'}, // Closed
          {localId: 1, projectName: 'proj'}, // Open
          {localId: 4, projectName: 'proj'}, // Closed
          {localId: 3, projectName: 'proj'}, // Closed
          {localId: 332, projectName: 'chromium'}, // Open
        ],
      },
      relatedIssues: relatedIssues,
    };
    assert.deepEqual(issue.sortedBlockedOn(statePreservesArrayOrder),
      [
        {localId: 1, projectName: 'proj', statusRef: {meansOpen: true}},
        {localId: 332, projectName: 'chromium', statusRef: {meansOpen: true}},
        {localId: 5, projectName: 'proj', statusRef: {meansOpen: false}},
        {localId: 4, projectName: 'proj', statusRef: {meansOpen: false}},
        {localId: 3, projectName: 'proj', statusRef: {meansOpen: false}},
      ]
    );
  });

  test('fieldValueMap', () => {
    assert.deepEqual(issue.fieldValueMap({}), new Map());
    assert.deepEqual(issue.fieldValueMap({issue: {
      fieldValues: [],
    }}), new Map());
    assert.deepEqual(issue.fieldValueMap({
      issue: {fieldValues: [
        {fieldRef: {fieldName: 'hello'}, value: 'v1'},
        {fieldRef: {fieldName: 'hello'}, value: 'v2'},
        {fieldRef: {fieldName: 'world'}, value: 'v3'},
      ]},
    }), new Map([
      ['hello', ['v1', 'v2']],
      ['world', ['v3']],
    ]));
  });

  test('fieldDefs', () => {
    assert.deepEqual(issue.fieldDefs({project: {}}), []);

    // Remove approval-related fields, regardless of issue.
    assert.deepEqual(issue.fieldDefs({project: {config: {
      fieldDefs: [
        {fieldRef: {fieldName: 'test', type: fieldTypes.INT_TYPE}},
        {fieldRef: {fieldName: 'ignoreMe', type: fieldTypes.APPROVAL_TYPE}},
        {fieldRef: {fieldName: 'LookAway', approvalName: 'ThisIsAnApproval'}},
        {fieldRef: {fieldName: 'phaseField'}, isPhaseField: true},
      ],
    }}}), [
      {fieldRef: {fieldName: 'test', type: fieldTypes.INT_TYPE}},
    ]);

    // Filter defs by applicableType.
    assert.deepEqual(issue.fieldDefs({
      project: {config: {
        fieldDefs: [
          {fieldRef: {fieldName: 'intyInt', type: fieldTypes.INT_TYPE}},
          {fieldRef: {fieldName: 'enum', type: fieldTypes.ENUM_TYPE}},
          {fieldRef: {fieldName: 'nonApplicable', type: fieldTypes.STR_TYPE},
            applicableType: 'None'},
          {fieldRef: {fieldName: 'defectsOnly', type: fieldTypes.STR_TYPE},
            applicableType: 'Defect'},
        ],
      }},
      issue: {
        fieldValues: [
          {fieldRef: {fieldName: 'Type'}, value: 'Defect'},
        ],
      },
    }), [
      {fieldRef: {fieldName: 'intyInt', type: fieldTypes.INT_TYPE}},
      {fieldRef: {fieldName: 'enum', type: fieldTypes.ENUM_TYPE}},
      {fieldRef: {fieldName: 'defectsOnly', type: fieldTypes.STR_TYPE},
        applicableType: 'Defect'},
    ]);
  });
});
