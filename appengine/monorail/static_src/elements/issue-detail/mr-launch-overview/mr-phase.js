// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import 'elements/chops/chops-dialog/chops-dialog.js';
import {store, connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import * as project from 'elements/reducers/project.js';
import '../mr-approval-card/mr-approval-card.js';
import {valuesForField} from
  'elements/issue-detail/metadata/shared/metadata-helpers.js';
import 'elements/issue-detail/metadata/mr-edit-metadata/mr-edit-metadata.js';
import 'elements/issue-detail/metadata/mr-metadata/mr-field-values.js';
import {SHARED_STYLES} from 'elements/shared/shared-styles.js';

const TARGET_PHASE_MILESTONE_MAP = {
  'Beta': 'feature_freeze',
  'Stable-Exp': 'final_beta_cut',
  'Stable': 'stable_cut',
  'Stable-Full': 'stable_cut',
};

const APPROVED_PHASE_MILESTONE_MAP = {
  'Beta': 'earliest_beta',
  'Stable-Exp': 'final_beta',
  'Stable': 'stable_date',
  'Stable-Full': 'stable_date',
};

// See monorail:4692 and the use of PHASES_WITH_MILESTONES
// in tracker/issueentry.py
const PHASES_WITH_MILESTONES = ['Beta', 'Stable', 'Stable-Exp', 'Stable-Full'];

/**
 * `<mr-phase>`
 *
 * This is the component for a single phase.
 *
 */
export class MrPhase extends connectStore(LitElement) {
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        :host {
          display: block;
        }
        chops-dialog {
          --chops-dialog-theme: {
            width: 500px;
            max-width: 100%;
          };
        }
        h2 {
          margin: 0;
          font-size: var(--chops-large-font-size);
          font-weight: normal;
          padding: 0.5em 8px;
          box-sizing: border-box;
          display: flex;
          align-items: center;
          flex-direction: row;
          justify-content: space-between;
        }
        h2 em {
          margin-left: 16px;
          font-size: var(--chops-main-font-size);
        }
        .chip {
          display: inline-block;
          font-size: var(--chops-main-font-size);
          padding: 0.25em 8px;
          margin: 0 2px;
          border-radius: 16px;
          background: var(--chops-blue-gray-50);
        }
        .phase-edit {
          padding: 0.1em 8px;
        }
      `,
    ];
  }

  render() {
    const isPhaseWithMilestone = PHASES_WITH_MILESTONES.includes(this.phaseName);
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <h2>
        <div>
          Approvals<span ?hidden=${!this.phaseName || !this.phaseName.length}>:
            ${this.phaseName}
          </span>
          ${isPhaseWithMilestone ? html`${this.fieldDefs
            && this.fieldDefs.map((field) => html`
              <div class="chip">
                ${field.fieldRef.fieldName}:
                <mr-field-values
                  .name=${field.fieldRef.fieldName}
                  .type=${field.fieldRef.type}
                  .values=${valuesForField(this.fieldValueMap, field.fieldRef.fieldName, this.phaseName)}
                  .projectName=${this.issueRef.projectName}
                ></mr-field-values>
              </div>
            `)}
            <em ?hidden=${!this._nextDate}>
              ${this._dateDescriptor}
              <chops-timestamp .timestamp=${this._nextDate}></chops-timestamp>
            </em>
          `: ''}
        </div>
        ${isPhaseWithMilestone ? html`
          <chops-button @click=${this.edit} class="de-emphasized phase-edit">
            <i class="material-icons">create</i>
            Edit
          </chops-button>
        `: ''}
      </h2>
      ${this.approvals && this.approvals.map((approval) => html`
        <mr-approval-card
          .approvers=${approval.approverRefs}
          .setter=${approval.setterRef}
          .fieldName=${approval.fieldRef.fieldName}
          .phaseName=${this.phaseName}
          .statusEnum=${approval.status}
          .survey=${approval.survey}
          .surveyTemplate=${approval.surveyTemplate}
          .urls=${approval.urls}
          .labels=${approval.labels}
          .users=${approval.users}
        ></mr-approval-card>
      `)}
      ${!this.approvals || !this.approvals.length ? html`No tasks for this phase.` : ''}
      // TODO(ehmaldonado): Move to /issue-detail/dialogs
      <chops-dialog id="editPhase" aria-labelledby="phaseDialogTitle">
        <h3 id="phaseDialogTitle" class="medium-heading">
          Editing phase: ${this.phaseName}
        </h3>
        <mr-edit-metadata
          id="metadataForm"
          class="edit-actions-right"
          .formName=${this.phaseName}
          .fieldDefs=${this.fieldDefs}
          .fieldValues=${this.fieldValues}
          .phaseName=${this.phaseName}
          ?disabled=${this.updatingIssue}
          .error=${this.updateIssueError && this.updateIssueError.description}
          @save=${this.save}
          @discard=${this.cancel}
          isApproval
          disableAttachments
        ></mr-edit-metadata>
      </chops-dialog>
    `;
  }

  static get properties() {
    return {
      issue: {type: Object},
      issueRef: {type: Object},
      phaseName: {type: String},
      updatingIssue: {type: Boolean},
      updateIssueError: {type: Object},
      approvals: {type: Array},
      fieldDefs: {type: Array},
      fieldValueMap: {type: Object},
      _milestoneData: {type: Object},
    };
  }

  stateChanged(state) {
    this.fieldValueMap = issue.fieldValueMap(state);
    this.issue = issue.issue(state);
    this.issueRef = issue.issueRef(state);
    this.updatingIssue = issue.requests(state).update.requesting;
    this.updateIssueError = issue.requests(state).update.error;
    this.fieldDefs = project.fieldDefsForPhases(state);
  }

  updated(changedProperties) {
    if (changedProperties.has('issue')) {
      this.reset();
    }
    if (changedProperties.has('updatingIssue')) {
      if (!this.updatingIssue && !this.updateIssueError) {
        // Close phase edit modal only after a request finishes without errors.
        this.cancel();
      }
    }

    if (changedProperties.has('fieldValueMap') || changedProperties.has('phaseName')) {
      const oldFieldValueMap = changedProperties.has('fieldValueMap') ?
        changedProperties.get('fieldValueMap') :
        this.fieldValueMap;
      const oldPhaseName = changedProperties.has('phaseName') ?
        changedProperties.get('phaseName') :
        this.phaseName;
      const oldMilestone = _fetchedMilestone(oldFieldValueMap, oldPhaseName);
      const milestone = _fetchedMilestone(this.fieldValueMap, this.phaseName);

      if (milestone && milestone !== oldMilestone) {
        window.fetch(
          `https://chromepmo.appspot.com/schedule/mstone/json?mstone=${milestone}`
        ).then((resp) => resp.json()).then((resp) => {
          this._milestoneData = resp;
        });
      }
    }
  }

  edit() {
    this.reset();
    this.shadowRoot.querySelector('#editPhase').open();
  }

  cancel() {
    this.shadowRoot.querySelector('#editPhase').close();
    this.reset();
  }

  reset() {
    const form = this.shadowRoot.querySelector('#metadataForm');
    form.reset();
  }

  save() {
    const form = this.shadowRoot.querySelector('#metadataForm');
    const delta = form.delta;

    if (delta.fieldValsAdd) {
      delta.fieldValsAdd = delta.fieldValsAdd.map(
        (fv) => Object.assign({phaseRef: {phaseName: this.phaseName}}, fv));
    }
    if (delta.fieldValsRemove) {
      delta.fieldValsRemove = delta.fieldValsRemove.map(
        (fv) => Object.assign({phaseRef: {phaseName: this.phaseName}}, fv));
    }

    const message = {
      issueRef: this.issueRef,
      delta: delta,
      sendEmail: form.sendEmail,
      commentContent: form.getCommentContent(),
    };

    if (message.commentContent || message.delta) {
      store.dispatch(issue.update(message));
    }
  }

  get _nextDate() {
    const phaseName = this.phaseName;
    const status = this._status;
    let data = this._milestoneData && this._milestoneData.mstones;
    // Data pulled from https://chromepmo.appspot.com/schedule/mstone/json?mstone=xx
    if (!phaseName || !status || !data || !data.length) return 0;
    data = data[0];

    let key = TARGET_PHASE_MILESTONE_MAP[phaseName];
    if (['Approved', 'Launched'].includes(status)) {
      key = APPROVED_PHASE_MILESTONE_MAP[phaseName];
    }
    if (!key || !(key in data)) return 0;
    return Math.floor((new Date(data[key])).getTime() / 1000);
  }

  get _dateDescriptor() {
    const status = this._status;
    if (status === 'Approved') {
      return 'Launching on ';
    } else if (status === 'Launched') {
      return 'Launched on ';
    }
    return 'Due by ';
  }

  get _status() {
    const target = _targetMilestone(this.fieldValueMap, this.phaseName);
    const approved = _approvedMilestone(this.fieldValueMap, this.phaseName);
    const launched = _launchedMilestone(this.fieldValueMap, this.phaseName);
    if (approved >= target) {
      if (launched >= approved) {
        return 'Launched';
      }
      return 'Approved';
    }
    return 'Target';
  }
}

function _milestoneFieldValue(fieldValueMap, phaseName, fieldName) {
  const values = valuesForField(fieldValueMap, fieldName, phaseName);
  return values.length ? values[0] : undefined;
}

function _approvedMilestone(fieldValueMap, phaseName) {
  return _milestoneFieldValue(fieldValueMap, phaseName,
    'M-Approved');
}

function _launchedMilestone(fieldValueMap, phaseName) {
  return _milestoneFieldValue(fieldValueMap, phaseName,
    'M-Launched');
}

function _targetMilestone(fieldValueMap, phaseName) {
  return _milestoneFieldValue(fieldValueMap, phaseName,
    'M-Target');
}

function _fetchedMilestone(fieldValueMap, phaseName) {
  const target = _targetMilestone(fieldValueMap, phaseName);
  const approved = _approvedMilestone(fieldValueMap, phaseName);
  const launched = _launchedMilestone(fieldValueMap, phaseName);
  return Math.max(target || 0, approved || 0, launched || 0);
}

customElements.define('mr-phase', MrPhase);
