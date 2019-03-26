// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import {ReduxMixin, actionCreator} from '../../redux/redux-mixin.js';
import * as issue from '../../redux/issue.js';
import * as project from '../../redux/project.js';
import './mr-edit-metadata.js';
import '../../shared/mr-shared-styles.js';

// Match: projectName:localIdFormat
const ISSUE_ID_REGEX = /(?:([a-z0-9-]+):)?(\d+)/i;

/**
 * `<mr-edit-issue>`
 *
 * Issue editing form.
 *
 */
export class MrEditIssue extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <style include="mr-shared-styles">
        h2 a {
          text-decoration: none;
        }
      </style>
      <h2 id="makechanges" class="medium-heading">
        <a href="#makechanges">Add a comment and make changes</a>
      </h2>
      <mr-edit-metadata
        form-name="Issue Edit"
        owner-name="[[_omitEmptyDisplayName(issue.ownerRef.displayName)]]"
        cc="[[issue.ccRefs]]"
        status="[[issue.statusRef.status]]"
        statuses="[[projectConfig.statusDefs]]"
        summary="[[issue.summary]]"
        components="[[issue.componentRefs]]"
        field-defs="[[_fieldDefs]]"
        field-values="[[issue.fieldValues]]"
        blocked-on="[[issue.blockedOnIssueRefs]]"
        blocking="[[issue.blockingIssueRefs]]"
        merged-into="[[issue.mergedIntoIssueRef]]"
        label-names="[[_labelNames]]"
        derived-labels="[[_derivedLabels]]"
        on-save="save"
        on-discard="reset"
        on-change="_presubmitIssue"
        disabled="[[updatingIssue]]"
        error="[[updateIssueError.description]]"
      ></mr-edit-metadata>
    `;
  }

  static get is() {
    return 'mr-edit-issue';
  }

  static get properties() {
    return {
      issue: {
        type: Object,
        observer: 'reset',
      },
      issueId: Number,
      projectName: String,
      projectConfig: Object,
      updatingIssue: Boolean,
      updateIssueError: Object,
      focusId: {
        type: String,
        observer: '_focusIdChanged',
      },
      _labelNames: {
        type: Array,
        computed: '_computeLabelNames(issue.labelRefs)',
      },
      _derivedLabels: {
        type: Array,
        computed: '_computeDerivedLabels(issue.labelRefs)',
      },
      _fieldDefs: Array,
    };
  }

  static mapStateToProps(state, element) {
    return {
      issue: state.issue,
      issueId: state.issueId,
      projectName: state.projectName,
      projectConfig: project.project(state).config,
      updatingIssue: state.requests.updateIssue.requesting,
      updateIssueError: state.requests.updateIssue.error,
      focusId: state.focusId,
      _fieldDefs: issue.fieldDefs(state),
    };
  }

  reset() {
    this.shadowRoot.querySelector('mr-edit-metadata').reset();
  }

  async save() {
    const form = this.shadowRoot.querySelector('mr-edit-metadata');
    const message = {
      issueRef: {
        projectName: this.projectName,
        localId: this.issueId,
      },
      delta: form.getDelta(),
      commentContent: form.getCommentContent(),
      sendEmail: form.sendEmail,
    };

    // Add files to message.
    const uploads = await form.getAttachments();

    if (uploads && uploads.length) {
      message.uploads = uploads;
    }

    if (message.commentContent || message.delta || message.uploads) {
      this.dispatchAction(actionCreator.updateIssue(message));
    }
  }

  focus() {
    const editHeader = this.shadowRoot.querySelector('#makechanges');
    editHeader.scrollIntoView();

    const editForm = this.shadowRoot.querySelector('mr-edit-metadata');
    editForm.focus();
  }

  _focusIdChanged(focusId) {
    if (!focusId) return;
    // TODO(zhangtiff): Generalize logic to focus elements based on ID
    // to a reuseable class mixin.
    if (focusId.toLowerCase() === 'makechanges') {
      this.focus();
    }
  }

  _computeLabelNames(labels) {
    if (!labels) return [];
    return labels.filter((l) => !l.isDerived).map((l) => l.label);
  }

  _computeDerivedLabels(labels) {
    if (!labels) return [];
    return labels.filter((l) => l.isDerived).map((l) => l.label);
  }

  _omitEmptyDisplayName(displayName) {
    return displayName === '----' ? '' : displayName;
  }

  _presubmitIssue(evt) {
    const message = {
      issueRef: {
        projectName: this.projectName,
        localId: this.issueId,
      },
      issueDelta: evt.detail.delta,
    };
    this.dispatchAction(actionCreator.presubmitIssue(message));
  }
}

customElements.define(MrEditIssue.is, MrEditIssue);
