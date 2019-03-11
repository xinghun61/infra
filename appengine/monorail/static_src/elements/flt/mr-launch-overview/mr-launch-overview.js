// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import {ReduxMixin, actionCreator} from '../../redux/redux-mixin.js';
import './mr-phase.js';
import './mr-convert-issue.js';

const ISSUE_EDIT_PERMISSION = 'editissue';

/**
 * `<mr-launch-overview>`
 *
 * This is a shorthand view of the phases for a user to see a quick overview.
 *
 */
export class MrLaunchOverview extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      <style>
        :host {
          width: 100%;
          display: flex;
          flex-flow: column;
          justify-content: flex-start;
          align-items: stretch;
        }
        mr-phase {
          margin-bottom: 0.75em;
        }
      </style>
      <template is="dom-repeat" items="[[phases]]" as="phase">
        <mr-phase phase-name="[[phase.phaseRef.phaseName]]" approvals="[[_approvalsForPhase(approvals, phase.phaseRef.phaseName)]]"></mr-phase>
      </template>
      <template is="dom-if" if="[[_phaselessApprovals.length]]">
        <mr-phase approvals="[[_phaselessApprovals]]"></mr-phase>
      </template>
      <template is="dom-if" if="[[_shouldOfferConvert(issuePermissions, projectTemplates)]]">
        <chops-button
          on-click="openConvertIssue">
          <i class="material-icons">transform</i>
          Convert this issue
        </chops-button>
      </template>
      <chops-dialog id="convertIssueDialog">
        <mr-convert-issue
          id="convertIssueForm"
          convert-issue-error=[[convertIssueError]]
          project-templates=[[projectTemplates]]
          on-discard="closeConvertIssue"
          on-save="saveConvertIssue"
        >
        </mr-convert-issue>
      </chops-dialog>
    `;
  }

  static get is() {
    return 'mr-launch-overview';
  }

  static get properties() {
    return {
      approvals: Array,
      phases: Array,
      _phaselessApprovals: {
        type: Array,
        computed: '_approvalsForPhase(approvals)',
      },
      convertingIssue: {
        type: Boolean,
        observer: '_convertingIssueChanged',
      },
      convertIssueError: Object,
      issueId: Number,
      issuePermissions: Object,
      projectName: String,
      projectTemplates: Array,
    };
  }

  static mapStateToProps(state, element) {
    if (!state.issue) return;
    return {
      approvals: state.issue.approvalValues,
      phases: state.issue.phases,
      convertingIssue: state.requests.convertIssue.requesting,
      convertIssueError: state.requests.convertIssue.error,
      issueId: state.issueId,
      issuePermissions: state.issuePermissions,
      projectName: state.projectName,
      projectTemplates: state.projectTemplates,
    };
  }

  _approvalsForPhase(approvals, phaseName) {
    return (approvals || []).filter((a) => {
      // We can assume phase names will be unique.
      return a.phaseRef.phaseName == phaseName;
    });
  }

  openConvertIssue() {
    this.$.convertIssueDialog.open();
  }

  closeConvertIssue() {
    this.$.convertIssueDialog.close();
  }

  saveConvertIssue() {
    actionCreator.convertIssue(this.dispatchAction.bind(this), {
      issueRef: {
        projectName: this.projectName,
        localId: this.issueId,
      },
      templateName: this.$.convertIssueForm.selectedTemplate,
      commentContent: this.$.convertIssueForm.$.commentContent.value,
      sendEmail: this.$.convertIssueForm.sendEmail,
    });
  }

  _shouldOfferConvert(issuePermissions, projectTemplates) {
    if (!issuePermissions || !projectTemplates) return false;
    return issuePermissions.includes(ISSUE_EDIT_PERMISSION) && projectTemplates.length;
  }

  _convertingIssueChanged(isConversionInFlight) {
    if (!isConversionInFlight && !this.convertIssueError) {
      this.$.convertIssueDialog.close();
    }
  }

}
customElements.define(MrLaunchOverview.is, MrLaunchOverview);
