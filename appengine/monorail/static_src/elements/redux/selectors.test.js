// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {selectors} from './selectors.js';
import {fieldTypes} from '../shared/field-types.js';

suite('selectors', () => {
  test('viewedIssue', () => {
    assert.isUndefined(selectors.viewedIssue({}));
    assert.deepEqual(selectors.viewedIssue({issue: {localId: 100}}),
      {localId: 100});
  });

  test('issueFieldValues', () => {
    assert.isUndefined(selectors.issueFieldValues({}));
    assert.isUndefined(selectors.issueFieldValues({issue: {}}));
    assert.deepEqual(selectors.issueFieldValues({
      issue: {fieldValues: [{value: 'v'}]},
    }), [{value: 'v'}]);
  });

  test('issueType', () => {
    assert.isUndefined(selectors.issueType({}));
    assert.isUndefined(selectors.issueType({issue: {}}));
    assert.isUndefined(selectors.issueType({
      issue: {fieldValues: [{value: 'v'}]},
    }));
    assert.deepEqual(selectors.issueType({
      issue: {fieldValues: [
        {fieldRef: {fieldName: 'IgnoreMe'}, value: 'v'},
        {fieldRef: {fieldName: 'Type'}, value: 'Defect'},
      ]},
    }), 'Defect');
  });

  test('issueRestrictions', () => {
    assert.deepEqual(selectors.issueRestrictions({}), {});
    assert.deepEqual(selectors.issueRestrictions(
      {issue: {}}), {});
    assert.deepEqual(selectors.issueRestrictions(
      {issue: {labelRefs: []}}), {});

    assert.deepEqual(selectors.issueRestrictions({issue: {labelRefs: [
      {label: 'IgnoreThis'},
      {label: 'IgnoreThis2'},
    ]}}), {});

    assert.deepEqual(selectors.issueRestrictions({issue: {labelRefs: [
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

  test('issueIsRestricted', () => {
    assert.isFalse(selectors.issueIsRestricted({}));
    assert.isFalse(selectors.issueIsRestricted({}));
    assert.isFalse(selectors.issueIsRestricted({issue: {}}));
    assert.isFalse(selectors.issueIsRestricted({issue: {labelRefs: []}}));

    assert.isTrue(selectors.issueIsRestricted({issue: {labelRefs: [
      {label: 'IgnoreThis'},
      {label: 'IgnoreThis2'},
      {label: 'Restrict-View-Google'},
    ]}}));

    assert.isFalse(selectors.issueIsRestricted({issue: {labelRefs: [
      {label: 'IgnoreThis'},
      {label: 'IgnoreThis2'},
      {label: 'Restrict-View'},
      {label: 'Restrict'},
      {label: 'RestrictView'},
      {label: 'Restt-View'},
    ]}}));

    assert.isTrue(selectors.issueIsRestricted({issue: {labelRefs: [
      {label: 'restrict-view-google'},
    ]}}));

    assert.isTrue(selectors.issueIsRestricted({issue: {labelRefs: [
      {label: 'restrict-EditIssue-world'},
    ]}}));

    assert.isTrue(selectors.issueIsRestricted({issue: {labelRefs: [
      {label: 'RESTRICT-ADDISSUECOMMENT-everyone'},
    ]}}));
  });

  test('issueIsOpen', () => {
    assert.isFalse(selectors.issueIsOpen({}));
    assert.isTrue(selectors.issueIsOpen(
      {issue: {statusRef: {meansOpen: true}}}));
    assert.isFalse(selectors.issueIsOpen(
      {issue: {statusRef: {meansOpen: false}}}));
  });

  test('issueBlockingIssues', () => {
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
    assert.deepEqual(selectors.issueBlockingIssues(stateNoReferences),
      [{localId: 1, projectName: 'proj'}]
    );

    const stateNoIssues = {
      issue: {
        blockingIssueRefs: [],
      },
      relatedIssues: relatedIssues,
    };
    assert.deepEqual(selectors.issueBlockingIssues(stateNoIssues), []);

    const stateIssuesWithReferences = {
      issue: {
        blockingIssueRefs: [
          {localId: 1, projectName: 'proj'},
          {localId: 332, projectName: 'chromium'},
        ],
      },
      relatedIssues: relatedIssues,
    };
    assert.deepEqual(selectors.issueBlockingIssues(stateIssuesWithReferences),
      [
        {localId: 1, projectName: 'proj', labelRefs: [{label: 'label'}]},
        {localId: 332, projectName: 'chromium', labelRefs: []},
      ]);
  });

  test('issueBlockedOnIssues', () => {
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
    assert.deepEqual(selectors.issueBlockedOnIssues(stateNoReferences),
      [{localId: 1, projectName: 'proj'}]
    );

    const stateNoIssues = {
      issue: {
        blockedOnIssueRefs: [],
      },
      relatedIssues: relatedIssues,
    };
    assert.deepEqual(selectors.issueBlockedOnIssues(stateNoIssues), []);

    const stateIssuesWithReferences = {
      issue: {
        blockedOnIssueRefs: [
          {localId: 1, projectName: 'proj'},
          {localId: 332, projectName: 'chromium'},
        ],
      },
      relatedIssues: relatedIssues,
    };
    assert.deepEqual(selectors.issueBlockedOnIssues(stateIssuesWithReferences),
      [
        {localId: 1, projectName: 'proj', labelRefs: [{label: 'label'}]},
        {localId: 332, projectName: 'chromium', labelRefs: []},
      ]);
  });

  test('issueSortedBlockedOn', () => {
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
    assert.deepEqual(selectors.issueSortedBlockedOn(stateNoReferences), [
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
    assert.deepEqual(selectors.issueSortedBlockedOn(stateReferences), [
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
    assert.deepEqual(selectors.issueSortedBlockedOn(statePreservesArrayOrder),
      [
        {localId: 1, projectName: 'proj', statusRef: {meansOpen: true}},
        {localId: 332, projectName: 'chromium', statusRef: {meansOpen: true}},
        {localId: 5, projectName: 'proj', statusRef: {meansOpen: false}},
        {localId: 4, projectName: 'proj', statusRef: {meansOpen: false}},
        {localId: 3, projectName: 'proj', statusRef: {meansOpen: false}},
      ]
    );
  });

  test('issueFieldValueMap', () => {
    assert.deepEqual(selectors.issueFieldValueMap({}), new Map());
    assert.deepEqual(selectors.issueFieldValueMap({issue: {
      fieldValues: [],
    }}), new Map());
    assert.deepEqual(selectors.issueFieldValueMap({
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

  test('fieldDefsForIssue', () => {
    assert.deepEqual(selectors.fieldDefsForIssue({project: {}}), []);

    // Remove approval-related fields, regardless of issue.
    assert.deepEqual(selectors.fieldDefsForIssue({project: {config: {
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
    assert.deepEqual(selectors.fieldDefsForIssue({
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
