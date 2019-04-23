// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import {store, connectStore} from '../../redux/base.js';
import * as issue from '../../redux/issue.js';
import * as project from '../../redux/project.js';
import * as ui from '../../redux/ui.js';
import './mr-edit-metadata.js';
import '../../shared/mr-shared-styles.js';


/**
 * `<mr-edit-issue>`
 *
 * Issue editing form.
 *
 */
export class MrEditIssue extends connectStore(PolymerElement) {
  static get template() {
    return html`
      <style include="mr-shared-styles">
        h2 a {
          text-decoration: none;
          color: var(--mr-content-heading-color);
        }
      </style>
      <h2 id="makechanges" class="medium-heading">
        <a href="#makechanges">Add a comment and make changes</a>
      </h2>
      <mr-edit-metadata
        form-name="Issue Edit"
        owner-name="[[_ownerDisplayName(issue.ownerRef)]]"
        cc="[[issue.ccRefs]]"
        status="[[issue.statusRef.status]]"
        statuses="[[_computeStatuses(projectConfig.statusDefs, issue.statusRef)]]"
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
        observer: '_resetConditionally',
      },
      issueRef: Object,
      projectConfig: Object,
      updatingIssue: Boolean,
      updateIssueError: Object,
      focusId: {
        type: String,
        observer: '_focusIdChanged',
      },
      _resetOnChange: Boolean,
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

  stateChanged(state) {
    this.setProperties({
      issue: issue.issue(state),
      issueRef: issue.issueRef(state),
      projectConfig: project.project(state).config,
      updatingIssue: issue.requests(state).update.requesting,
      updateIssueError: issue.requests(state).update.error,
      focusId: ui.focusId(state),
      _fieldDefs: issue.fieldDefs(state),
    });
  }

  reset() {
    this.shadowRoot.querySelector('mr-edit-metadata').reset();
  }

  async save() {
    this._resetOnChange = true;
    const form = this.shadowRoot.querySelector('mr-edit-metadata');
    const message = {
      issueRef: this.issueRef,
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
      store.dispatch(issue.update(message));
    }
  }

  focus() {
    const editHeader = this.shadowRoot.querySelector('#makechanges');
    editHeader.scrollIntoView();

    const editForm = this.shadowRoot.querySelector('mr-edit-metadata');
    editForm.focus();
  }

  _resetConditionally() {
    if (this._resetOnChange) {
      this._resetOnChange = false;
      this.reset();
    }
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

  _ownerDisplayName(ownerRef) {
    return (ownerRef && ownerRef.userId) ? ownerRef.displayName : '';
  }

  _presubmitIssue(evt) {
    const message = {
      issueRef: this.issueRef,
      issueDelta: evt.detail.delta,
    };
    store.dispatch(issue.presubmit(message));
  }

  _computeStatuses(statusDefsArg, currentStatusRef) {
    const statusDefs = statusDefsArg || [];
    if (!currentStatusRef || statusDefs.find(
      (status) => status.status === currentStatusRef.status)) return statusDefs;
    return [currentStatusRef, ...statusDefs];
  }
}

customElements.define(MrEditIssue.is, MrEditIssue);
