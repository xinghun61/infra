// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import * as issue from './issue.js';
import {fieldTypes} from '../shared/field-types.js';

suite('issue', () => {
  test('issue', () => {
    assert.deepEqual(issue.issue(wrapIssue()), {});
    assert.deepEqual(issue.issue(wrapIssue({localId: 100})), {localId: 100});
  });

  test('fieldValues', () => {
    assert.isUndefined(issue.fieldValues(wrapIssue()));
    assert.deepEqual(issue.fieldValues(wrapIssue({
      fieldValues: [{value: 'v'}],
    })), [{value: 'v'}]);
  });

  test('type', () => {
    assert.isUndefined(issue.type(wrapIssue()));
    assert.isUndefined(issue.type(wrapIssue({
      fieldValues: [{value: 'v'}],
    })));
    assert.deepEqual(issue.type(wrapIssue({
      fieldValues: [
        {fieldRef: {fieldName: 'IgnoreMe'}, value: 'v'},
        {fieldRef: {fieldName: 'Type'}, value: 'Defect'},
      ],
    })), 'Defect');
  });

  test('restrictions', () => {
    assert.deepEqual(issue.restrictions(wrapIssue()), {});
    assert.deepEqual(issue.restrictions(wrapIssue({labelRefs: []})), {});

    assert.deepEqual(issue.restrictions(wrapIssue({labelRefs: [
      {label: 'IgnoreThis'},
      {label: 'IgnoreThis2'},
    ]})), {});

    assert.deepEqual(issue.restrictions(wrapIssue({labelRefs: [
      {label: 'IgnoreThis'},
      {label: 'IgnoreThis2'},
      {label: 'Restrict-View-Google'},
      {label: 'Restrict-EditIssue-hello'},
      {label: 'Restrict-EditIssue-test'},
      {label: 'Restrict-AddIssueComment-HELLO'},
    ]})), {
      'view': ['Google'],
      'edit': ['hello', 'test'],
      'comment': ['HELLO'],
    });
  });

  test('isRestricted', () => {
    assert.isFalse(issue.isRestricted(wrapIssue()));
    assert.isFalse(issue.isRestricted(wrapIssue({labelRefs: []})));

    assert.isTrue(issue.isRestricted(wrapIssue({labelRefs: [
      {label: 'IgnoreThis'},
      {label: 'IgnoreThis2'},
      {label: 'Restrict-View-Google'},
    ]})));

    assert.isFalse(issue.isRestricted(wrapIssue({labelRefs: [
      {label: 'IgnoreThis'},
      {label: 'IgnoreThis2'},
      {label: 'Restrict-View'},
      {label: 'Restrict'},
      {label: 'RestrictView'},
      {label: 'Restt-View'},
    ]})));

    assert.isTrue(issue.isRestricted(wrapIssue({labelRefs: [
      {label: 'restrict-view-google'},
    ]})));

    assert.isTrue(issue.isRestricted(wrapIssue({labelRefs: [
      {label: 'restrict-EditIssue-world'},
    ]})));

    assert.isTrue(issue.isRestricted(wrapIssue({labelRefs: [
      {label: 'RESTRICT-ADDISSUECOMMENT-everyone'},
    ]})));
  });

  test('isOpen', () => {
    assert.isFalse(issue.isOpen(wrapIssue()));
    assert.isTrue(issue.isOpen(wrapIssue({statusRef: {meansOpen: true}})));
    assert.isFalse(issue.isOpen(wrapIssue({statusRef: {meansOpen: false}})));
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
    const stateNoReferences = {issue: {
      currentIssue: {
        blockingIssueRefs: [{localId: 1, projectName: 'proj'}],
      },
      relatedIssues: new Map(),
    }};
    assert.deepEqual(issue.blockingIssues(stateNoReferences),
      [{localId: 1, projectName: 'proj'}]
    );

    const stateNoIssues = {issue: {
      currentIssue: {
        blockingIssueRefs: [],
      },
      relatedIssues: relatedIssues,
    }};
    assert.deepEqual(issue.blockingIssues(stateNoIssues), []);

    const stateIssuesWithReferences = {issue: {
      currentIssue: {
        blockingIssueRefs: [
          {localId: 1, projectName: 'proj'},
          {localId: 332, projectName: 'chromium'},
        ],
      },
      relatedIssues: relatedIssues,
    }};
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
    const stateNoReferences = {issue: {
      currentIssue: {
        blockedOnIssueRefs: [{localId: 1, projectName: 'proj'}],
      },
      relatedIssues: new Map(),
    }};
    assert.deepEqual(issue.blockedOnIssues(stateNoReferences),
      [{localId: 1, projectName: 'proj'}]
    );

    const stateNoIssues = {issue: {
      currentIssue: {
        blockedOnIssueRefs: [],
      },
      relatedIssues: relatedIssues,
    }};
    assert.deepEqual(issue.blockedOnIssues(stateNoIssues), []);

    const stateIssuesWithReferences = {issue: {
      currentIssue: {
        blockedOnIssueRefs: [
          {localId: 1, projectName: 'proj'},
          {localId: 332, projectName: 'chromium'},
        ],
      },
      relatedIssues: relatedIssues,
    }};
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
    const stateNoReferences = {issue: {
      currentIssue: {
        blockedOnIssueRefs: [
          {localId: 3, projectName: 'proj'},
          {localId: 1, projectName: 'proj'},
        ],
      },
      relatedIssues: new Map(),
    }};
    assert.deepEqual(issue.sortedBlockedOn(stateNoReferences), [
      {localId: 3, projectName: 'proj'},
      {localId: 1, projectName: 'proj'},
    ]);
    const stateReferences = {issue: {
      currentIssue: {
        blockedOnIssueRefs: [
          {localId: 3, projectName: 'proj'},
          {localId: 1, projectName: 'proj'},
        ],
      },
      relatedIssues: relatedIssues,
    }};
    assert.deepEqual(issue.sortedBlockedOn(stateReferences), [
      {localId: 1, projectName: 'proj', statusRef: {meansOpen: true}},
      {localId: 3, projectName: 'proj', statusRef: {meansOpen: false}},
    ]);
    const statePreservesArrayOrder = {issue: {
      currentIssue: {
        blockedOnIssueRefs: [
          {localId: 5, projectName: 'proj'}, // Closed
          {localId: 1, projectName: 'proj'}, // Open
          {localId: 4, projectName: 'proj'}, // Closed
          {localId: 3, projectName: 'proj'}, // Closed
          {localId: 332, projectName: 'chromium'}, // Open
        ],
      },
      relatedIssues: relatedIssues,
    }};
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
    assert.deepEqual(issue.fieldValueMap(wrapIssue()), new Map());
    assert.deepEqual(issue.fieldValueMap(wrapIssue({
      fieldValues: [],
    })), new Map());
    assert.deepEqual(issue.fieldValueMap(wrapIssue({
      fieldValues: [
        {fieldRef: {fieldName: 'hello'}, value: 'v1'},
        {fieldRef: {fieldName: 'hello'}, value: 'v2'},
        {fieldRef: {fieldName: 'world'}, value: 'v3'},
      ],
    })), new Map([
      ['hello', ['v1', 'v2']],
      ['world', ['v3']],
    ]));
  });

  test('fieldDefs', () => {
    assert.deepEqual(issue.fieldDefs({
      project: {},
      ...wrapIssue(),
    }), []);

    // Remove approval-related fields, regardless of issue.
    assert.deepEqual(issue.fieldDefs({
      project: {config: {
        fieldDefs: [
          {fieldRef: {fieldName: 'test', type: fieldTypes.INT_TYPE}},
          {fieldRef: {fieldName: 'ignoreMe', type: fieldTypes.APPROVAL_TYPE}},
          {fieldRef: {fieldName: 'LookAway', approvalName: 'ThisIsAnApproval'}},
          {fieldRef: {fieldName: 'phaseField'}, isPhaseField: true},
        ],
      }},
      ...wrapIssue(),
    }), [
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
      ...wrapIssue({
        fieldValues: [
          {fieldRef: {fieldName: 'Type'}, value: 'Defect'},
        ],
      }),
    }), [
      {fieldRef: {fieldName: 'intyInt', type: fieldTypes.INT_TYPE}},
      {fieldRef: {fieldName: 'enum', type: fieldTypes.ENUM_TYPE}},
      {fieldRef: {fieldName: 'defectsOnly', type: fieldTypes.STR_TYPE},
        applicableType: 'Defect'},
    ]);
  });
});

function wrapIssue(currentIssue) {
  return {issue: {currentIssue: {...currentIssue}}};
}
