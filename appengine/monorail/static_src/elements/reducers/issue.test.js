// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import * as issue from './issue.js';
import {fieldTypes} from 'elements/shared/field-types.js';
import {prpcClient} from 'prpc-client-instance.js';

let prpcCall;

describe('issue', () => {
  it('issue', () => {
    assert.deepEqual(issue.issue(wrapIssue()), {});
    assert.deepEqual(issue.issue(wrapIssue({localId: 100})), {localId: 100});
  });

  it('fieldValues', () => {
    assert.isUndefined(issue.fieldValues(wrapIssue()));
    assert.deepEqual(issue.fieldValues(wrapIssue({
      fieldValues: [{value: 'v'}],
    })), [{value: 'v'}]);
  });

  it('type computes type from custom field', () => {
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

  it('type computes type from label', () => {
    assert.deepEqual(issue.type(wrapIssue({
      labelRefs: [
        {label: 'Test'},
        {label: 'tYpE-FeatureRequest'},
      ],
    })), 'FeatureRequest');

    assert.deepEqual(issue.type(wrapIssue({
      fieldValues: [
        {fieldRef: {fieldName: 'IgnoreMe'}, value: 'v'},
      ],
      labelRefs: [
        {label: 'Test'},
        {label: 'Type-Defect'},
      ],
    })), 'Defect');
  });

  it('restrictions', () => {
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

  it('isOpen', () => {
    assert.isFalse(issue.isOpen(wrapIssue()));
    assert.isTrue(issue.isOpen(wrapIssue({statusRef: {meansOpen: true}})));
    assert.isFalse(issue.isOpen(wrapIssue({statusRef: {meansOpen: false}})));
  });

  it('blockingIssues', () => {
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

    const stateIssuesWithFederatedReferences = {issue: {
      currentIssue: {
        blockingIssueRefs: [
          {localId: 1, projectName: 'proj'},
          {extIdentifier: 'b/1234'},
        ],
      },
      relatedIssues: relatedIssues,
    }};
    assert.deepEqual(issue.blockingIssues(stateIssuesWithFederatedReferences),
      [
        {localId: 1, projectName: 'proj', labelRefs: [{label: 'label'}]},
        {extIdentifier: 'b/1234'},
      ]);
  });

  it('blockedOnIssues', () => {
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

    const stateIssuesWithFederatedReferences = {issue: {
      currentIssue: {
        blockedOnIssueRefs: [
          {localId: 1, projectName: 'proj'},
          {extIdentifier: 'b/1234'},
        ],
      },
      relatedIssues: relatedIssues,
    }};
    assert.deepEqual(issue.blockedOnIssues(stateIssuesWithFederatedReferences),
      [
        {localId: 1, projectName: 'proj', labelRefs: [{label: 'label'}]},
        {extIdentifier: 'b/1234'},
      ]);
  });

  it('sortedBlockedOn', () => {
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

  it('mergedInto', () => {
    assert.deepEqual(issue.mergedInto(wrapIssue()), {});
    assert.deepEqual(issue.mergedInto(wrapIssue({
      mergedIntoIssueRef: {localId: 22, projectName: 'proj'},
    })), {
      localId: 22,
      projectName: 'proj',
    });

    const merged = issue.mergedInto({
      issue: {
        currentIssue: {
          mergedIntoIssueRef: {localId: 22, projectName: 'proj'},
        },
        relatedIssues: new Map([
          ['proj:22', {localId: 22, projectName: 'proj', summary: 'test'}],
        ]),
      },
    });
    assert.deepEqual(merged, {
      localId: 22,
      projectName: 'proj',
      summary: 'test',
    });
  });

  it('fieldValueMap', () => {
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

  it('fieldDefs filters fields by applicable type', () => {
    assert.deepEqual(issue.fieldDefs({
      project: {},
      ...wrapIssue(),
    }), []);

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

  it('fieldDefs skips approval fields for all issues', () => {
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
  });

  it('fieldDefs includes non applicable fields when values defined', () => {
    assert.deepEqual(issue.fieldDefs({
      project: {config: {
        fieldDefs: [
          {fieldRef: {fieldName: 'nonApplicable', type: fieldTypes.STR_TYPE},
            applicableType: 'None'},
        ],
      }},
      ...wrapIssue({
        fieldValues: [
          {fieldRef: {fieldName: 'nonApplicable'}, value: 'v1'},
        ],
      }),
    }), [
      {fieldRef: {fieldName: 'nonApplicable', type: fieldTypes.STR_TYPE},
        applicableType: 'None'},
    ]);
  });

  describe('ListIssues', () => {
    beforeEach(() => {
      prpcCall = sinon.stub(prpcClient, 'call');
    });

    afterEach(() => {
      prpcCall.restore();
    });

    it('correct number of calls to ListIssues', async () => {
      prpcCall.callsFake(() => {
        return {
          issues: [{localId: 1}, {localId: 2}, {localId: 3}],
          totalResults: 6,
        };
      });

      const dispatch = sinon.stub();
      const action = issue.fetchIssueList('', '', {maxItems: 3}, 2);
      await action(dispatch);

      sinon.assert.calledTwice(prpcCall);
      sinon.assert.calledWith(dispatch, sinon.match({
        type: 'FETCH_ISSUE_LIST_SUCCESS',
        issueList: {
          issues:
            [{localId: 1}, {localId: 2}, {localId: 3},
              {localId: 1}, {localId: 2}, {localId: 3}],
          progress: 1,
          totalResults: 6,
        },
      }));
    });

    it('correct order of issues from fetchListIssues', async () => {
      prpcCall.onFirstCall().returns({issues: [{localId: 1}], totalResults: 6});
      prpcCall.onSecondCall().returns({
        issues: [{localId: 2}],
        totalResults: 6});
      prpcCall.onThirdCall().returns({issues: [{localId: 3}], totalResults: 6});

      const dispatch = sinon.stub();
      const action = issue.fetchIssueList('', '', {maxItems: 1}, 3);
      await action(dispatch);

      sinon.assert.calledWith(dispatch, sinon.match({
        type: 'FETCH_ISSUE_LIST_SUCCESS',
        issueList: {
          issues: [{localId: 1}, {localId: 2}, {localId: 3}],
          progress: 1,
          totalResults: 6,
        },
      }));
    });
  });
});

function wrapIssue(currentIssue) {
  return {issue: {currentIssue: {...currentIssue}}};
}
