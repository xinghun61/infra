// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import 'elements/chops/chops-snackbar/chops-snackbar.js';
import {store, connectStore} from 'reducers/base.js';
import * as issue from 'reducers/issue.js';
import * as project from 'reducers/project.js';
import * as ui from 'reducers/ui.js';
import {arrayToEnglish} from 'shared/helpers.js';
import {SHARED_STYLES} from 'shared/shared-styles.js';
import './mr-edit-metadata.js';

import ClientLogger from 'monitoring/client-logger.js';

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
    let blockedOnRefs = issue.blockedOnIssueRefs || [];
    if (issue.danglingBlockedOnRefs && issue.danglingBlockedOnRefs.length) {
      blockedOnRefs = blockedOnRefs.concat(issue.danglingBlockedOnRefs);
    }

    let blockingRefs = issue.blockingIssueRefs || [];
    if (issue.danglingBlockingRefs && issue.danglingBlockingRefs.length) {
      blockingRefs = blockingRefs.concat(issue.danglingBlockingRefs);
    }

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
        .blockedOn=${blockedOnRefs}
        .blocking=${blockingRefs}
        .mergedInto=${issue.mergedIntoIssueRef}
        .labelNames=${this._labelNames}
        .derivedLabels=${this._derivedLabels}
        .error=${this.updateError && (this.updateError.description || this.updateError.message)}
        ?saving=${this.updatingIssue}
        @save=${this.save}
        @discard=${this.reset}
        @change=${this._onChange}
      ></mr-edit-metadata>
    `;
  }

  static get properties() {
    return {
      /**
       * All comments, including descriptions.
       */
      comments: {
        type: Array,
      },
      /**
       * The issue being updated.
       */
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
      updateError: {
        type: Object,
      },
      focusId: {
        type: String,
      },
      _issueUpdated: {
        type: Boolean,
      },
      _awaitingSave: {
        type: Boolean,
      },
      _fieldDefs: {
        type: Array,
      },
    };
  }

  constructor() {
    super();

    this.clientLogger = new ClientLogger('issues');
  }

  stateChanged(state) {
    this.issue = issue.issue(state);
    this.issueRef = issue.issueRef(state);
    this.comments = issue.comments(state);
    this.projectConfig = project.project(state).config;
    this.updatingIssue = issue.requests(state).update.requesting;
    this.updateError = issue.requests(state).update.error;
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
      if (this._awaitingSave) {
        // This is the first update cycle after an issue update has finished
        // saving.
        this._awaitingSave = false;
        this._issueUpdated = true;
        this.reset();
      }
    }

    if (changedProperties.has('_issueUpdated') && this._issueUpdated) {
      // This case runs after the update cycle when the snackbar telling the
      // user their issue has been updates shows up.
      if (this.clientLogger.started('issue-update')) {
        this.clientLogger.logEnd('issue-update', 'computer-time', 120 * 1000);
      }
    }
  }

  reset() {
    const form = this.shadowRoot.querySelector('mr-edit-metadata');
    if (!form) return;
    form.reset();
  }

  async save() {
    const form = this.shadowRoot.querySelector('mr-edit-metadata');
    if (!form) return;

    const delta = form.delta;
    if (!_checkRemovedRestrictions(delta.labelRefsRemove)) {
      return;
    }

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
      this.clientLogger.logStart('issue-update', 'computer-time');

      this._issueUpdated = false;
      this._awaitingSave = true;

      store.dispatch(issue.update(message));
    }
  }

  focus() {
    const editHeader = this.shadowRoot.querySelector('#makechanges');
    editHeader.scrollIntoView();

    const editForm = this.shadowRoot.querySelector('mr-edit-metadata');
    editForm.focus();
  }

  get _commentsText() {
    return (this.comments || []).map(
        (comment) => comment.content).join('\n').trim();
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

  _presubmitIssue(issueDelta) {
    if (Object.keys(issueDelta).length) {
      const message = {
        issueDelta,
        issueRef: this.issueRef,
      };
      store.dispatch(issue.presubmit(message));
    }
  }

  _predictComponent(issueDelta, commentContent) {
    // Component prediction is only done on Chromium issues.
    if (this.issueRef.projectName !== 'chromium') return;

    let text = this._commentsText;
    if (issueDelta.summary) {
      text += '\n' + summary;
    } else if (this.issue.summary) {
      text += '\n' + this.issue.summary;
    }
    if (commentContent) {
      text += '\n' + commentContent.trim();
    }

    store.dispatch(issue.predictComponent(this.issueRef.projectName, text));
  }

  _onChange(evt) {
    this._presubmitIssue(evt.detail.delta);
    this._predictComponent(evt.detail.delta, evt.detail.commentContent);
  }

  _availableStatuses(statusDefsArg, currentStatusRef) {
    let statusDefs = statusDefsArg || [];
    statusDefs = statusDefs.filter((status) => !status.deprecated);
    if (!currentStatusRef || statusDefs.find(
        (status) => status.status === currentStatusRef.status)) {
      return statusDefs;
    }
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
