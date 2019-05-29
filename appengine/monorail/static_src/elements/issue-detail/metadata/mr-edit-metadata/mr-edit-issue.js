// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import 'elements/chops/chops-snackbar/chops-snackbar.js';
import {store, connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import * as project from 'elements/reducers/project.js';
import * as ui from 'elements/reducers/ui.js';
import {arrayToEnglish} from 'elements/shared/helpers.js';
import {SHARED_STYLES} from 'elements/shared/shared-styles.js';
import './mr-edit-metadata.js';

/**
 * `<mr-edit-issue>`
 *
 * Issue editing form.
 *
 */
export class MrEditIssue extends connectStore(LitElement) {
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        h2 a {
          text-decoration: none;
          color: var(--mr-content-heading-color);
        }
      `,
    ];
  }

  render() {
    const issue = this.issue || {};
    return html`
      <h2 id="makechanges" class="medium-heading">
        <a href="#makechanges">Add a comment and make changes</a>
      </h2>
      <chops-snackbar ?hidden=${!this._issueUpdated}>
        Your comment was added.
      </chops-snackbar>
      <mr-edit-metadata
        formName="Issue Edit"
        .ownerName=${this._ownerDisplayName(issue.ownerRef)}
        .cc=${issue.ccRefs}
        .status=${issue.statusRef && issue.statusRef.status}
        .statuses=${this._availableStatuses(this.projectConfig.statusDefs, this.issue.statusRef)}
        .summary=${issue.summary}
        .components=${issue.componentRefs}
        .fieldDefs=${this._fieldDefs}
        .fieldValues=${issue.fieldValues}
        .blockedOn=${issue.blockedOnIssueRefs}
        .blocking=${issue.blockingIssueRefs}
        .mergedInto=${issue.mergedIntoIssueRef}
        .labelNames=${this._labelNames}
        .derivedLabels=${this._derivedLabels}
        .disabled=${this.updatingIssue}
        .error=${this.updateIssueError && this.updateIssueError.description}
        @save=${this.save}
        @discard=${this.reset}
        @change=${this._presubmitIssue}
      ></mr-edit-metadata>
    `;
  }

  static get properties() {
    return {
      issue: {
        type: Object,
      },
      issueRef: {
        type: Object,
      },
      projectConfig: {
        type: Object,
      },
      updatingIssue: {
        type: Boolean,
      },
      updateIssueError: {
        type: Object,
      },
      focusId: {
        type: String,
      },
      _issueUpdated: {
        type: Boolean,
      },
      _resetOnChange: {
        type: Boolean,
      },
      _fieldDefs: {
        type: Array,
      },
    };
  }

  stateChanged(state) {
    this.issue = issue.issue(state);
    this.issueRef = issue.issueRef(state);
    this.projectConfig = project.project(state).config;
    this.updatingIssue = issue.requests(state).update.requesting;
    this.updateIssueError = issue.requests(state).update.error;
    this.focusId = ui.focusId(state);
    this._fieldDefs = issue.fieldDefs(state);
  }

  updated(changedProperties) {
    if (this.focusId && changedProperties.has('focusId')) {
      // TODO(zhangtiff): Generalize logic to focus elements based on ID
      // to a reuseable class mixin.
      if (this.focusId.toLowerCase() === 'makechanges') {
        this.focus();
      }
    }

    if (this.issue && changedProperties.has('issue')) {
      if (this._resetOnChange) {
        this._resetOnChange = false;
        this._issueUpdated = true;
        this.reset();
      }
    }
  }

  reset() {
    this.shadowRoot.querySelector('mr-edit-metadata').reset();
  }

  async save() {
    const form = this.shadowRoot.querySelector('mr-edit-metadata');
    const delta = form.delta;
    if (!_checkRemovedRestrictions(delta.labelRefsRemove)) {
      return;
    }

    this._issueUpdated = false;
    this._resetOnChange = true;
    const message = {
      issueRef: this.issueRef,
      delta: delta,
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

  get _labelNames() {
    if (!this.issue || !this.issue.labelRefs) return [];
    const labels = this.issue.labelRefs;
    return labels.filter((l) => !l.isDerived).map((l) => l.label);
  }

  get _derivedLabels() {
    if (!this.issue || !this.issue.labelRefs) return [];
    const labels = this.issue.labelRefs;
    return labels.filter((l) => l.isDerived).map((l) => l.label);
  }

  _ownerDisplayName(ownerRef) {
    return (ownerRef && ownerRef.userId) ? ownerRef.displayName : '';
  }

  _presubmitIssue(evt) {
    if (Object.keys(evt.detail.delta).length) {
      const message = {
        issueRef: this.issueRef,
        issueDelta: evt.detail.delta,
      };
      store.dispatch(issue.presubmit(message));
    }
  }

  _availableStatuses(statusDefsArg, currentStatusRef) {
    let statusDefs = statusDefsArg || [];
    statusDefs = statusDefs.filter((status) => !status.deprecated);
    if (!currentStatusRef || statusDefs.find(
      (status) => status.status === currentStatusRef.status)) return statusDefs;
    return [currentStatusRef, ...statusDefs];
  }
}

function _checkRemovedRestrictions(labelRefsRemove) {
  if (!labelRefsRemove) return true;
  const removedRestrictions = labelRefsRemove
    .map(({label}) => label)
    .filter((label) => label.toLowerCase().startsWith('restrict-'));
  const removeRestrictionsMessage =
    'You are removing these restrictions:\n' +
    arrayToEnglish(removedRestrictions) + '\n' +
    'This might allow more people to access this issue. Are you sure?';
  return !removedRestrictions.length || confirm(removeRestrictionsMessage);
}

customElements.define('mr-edit-issue', MrEditIssue);
