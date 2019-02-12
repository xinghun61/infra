// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import '../../chops/chops-dialog/chops-dialog.js';
import '@polymer/iron-collapse/iron-collapse.js';
import {selectors} from '../../redux/selectors.js';
import {ReduxMixin, actionType, actionCreator} from '../../redux/redux-mixin.js';
import {fieldTypes} from '../../shared/field-types.js';
import '../../mr-comment-content/mr-comment-content.js';
import '../mr-comments/mr-comments.js';
import '../mr-inline-editor/mr-inline-editor.js';
import '../mr-edit-metadata/mr-edit-metadata.js';
import '../mr-metadata/mr-metadata.js';
import '../shared/mr-flt-styles.js';

const APPROVER_RESTRICTED_STATUSES = new Set(
  ['NA', 'Approved', 'NotApproved']);

const STATUS_ENUM_TO_TEXT = {
  '': 'NotSet',
  'NEEDS_REVIEW': 'NeedsReview',
  'NA': 'NA',
  'REVIEW_REQUESTED': 'ReviewRequested',
  'REVIEW_STARTED': 'ReviewStarted',
  'NEED_INFO': 'NeedInfo',
  'APPROVED': 'Approved',
  'NOT_APPROVED': 'NotApproved',
};

const TEXT_TO_STATUS_ENUM = {
  'NotSet': 'NOT_SET',
  'NeedsReview': 'NEEDS_REVIEW',
  'NA': 'NA',
  'ReviewRequested': 'REVIEW_REQUESTED',
  'ReviewStarted': 'REVIEW_STARTED',
  'NeedInfo': 'NEED_INFO',
  'Approved': 'APPROVED',
  'NotApproved': 'NOT_APPROVED',
};

const STATUS_CLASS_MAP = {
  'NotSet': 'status-notset',
  'NeedsReview': 'status-pending',
  'NA': 'status-notset',
  'ReviewRequested': 'status-pending',
  'ReviewStarted': 'status-pending',
  'NeedInfo': 'status-pending',
  'Approved': 'status-approved',
  'NotApproved': 'status-rejected',
};

const STATUS_DOCSTRING_MAP = {
  'NotSet': '',
  'NeedsReview': 'Approval gate needs work',
  'NA': 'Approval gate not required',
  'ReviewRequested': 'Approval requested',
  'ReviewStarted': 'Approval in progress',
  'NeedInfo': 'Approval review needs more information',
  'Approved': 'Approved for Launch',
  'NotApproved': 'Not Approved for Launch',
};

const CLASS_ICON_MAP = {
  'status-notset': 'remove',
  'status-pending': 'autorenew',
  'status-approved': 'done',
  'status-rejected': 'close',
};

/**
 * `<mr-approval-card>`
 *
 * This element shows a card for a single approval.
 *
 */
export class MrApprovalCard extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      <style include="mr-flt-styles">
        :host {
          width: 100%;
          background-color: white;
          font-size: 85%;
          border-bottom: var(--chops-normal-border);
          box-sizing: border-box;
          display: block;
          border-left: 4px solid var(--approval-bg-color);
          --approval-bg-color: hsl(227, 20%, 92%);
          --approval-accent-color: hsl(227, 80%, 40%);
        }
        :host(.status-approved) {
          --approval-bg-color: hsl(78, 55%, 90%);
          --approval-accent-color: hsl(78, 100%, 30%);
        }
        :host(.status-pending) {
          --approval-bg-color: hsl(40, 75%, 90%);
          --approval-accent-color: hsl(33, 100%, 39%);
        }
        :host(.status-rejected) {
          --approval-bg-color: hsl(5, 60%, 92%);
          --approval-accent-color: hsl(357, 100%, 39%);
        }
        h3 {
          margin: 0;
          padding: 0;
          display: inline;
          font-weight: inherit;
          font-size: inherit;
          line-height: inherit;
        }
        mr-inline-editor {
          display: block;
          width: 100%;
          margin-bottom: 0.5em;
          color: hsl(0, 0%, 30%);
          box-sizing: border-box;
          word-wrap: break-word;
          --mr-inline-editor-textarea-min-height: 300px;
        }
        .approver-notice {
          padding: 0.25em 0;
          width: 100%;
          display: flex;
          align-items: baseline;
          justify-content: space-between;
          border-bottom: 1px dotted hsl(0, 0%, 83%);
        }
        .card-content {
          box-sizing: border-box;
          padding: 0.5em 16px;
          padding-bottom: 1em;
        }
        .expand-icon {
          display: block;
          margin-right: 8px;
          color: hsl(0, 0%, 45%);
        }
        .header {
          margin: 0;
          width: 100%;
          border: 0;
          font-size: 120%;
          font-weight: normal;
          box-sizing: border-box;
          display: flex;
          align-items: center;
          flex-direction: row;
          padding: 0.5em 8px;
          background-color: var(--approval-bg-color);
          cursor: pointer;
        }
        .status {
          font-size: 80%;
          color: var(--approval-accent-color);
          display: inline-flex;
          align-items: center;
          margin-left: 32px;
        }
        .survey {
          padding: 0.5em 0;
          max-height: 500px;
          overflow-y: auto;
          max-width: 100%;
          box-sizing: border-box;
        }
      </style>
      <button class="header" on-click="toggleCard" aria-expanded$="[[_toString(opened)]]">
        <i class="material-icons expand-icon">[[_expandIcon]]</i>
        <h3>[[fieldName]]</h3>
        <span class="status">
          <i class="material-icons status-icon">[[_statusIcon]]</i>
          [[_status]]
        </span>
      </button>
      <iron-collapse class="card-content" id="cardCollapse" opened="[[opened]]">
        <div class="approver-notice">
          <template is="dom-if" if="[[_isApprovalOwner]]">
            You are an approver for this bit.
          </template>
          <template is="dom-if" if="[[user.isSiteAdmin]]">
            Your site admin privileges give you full access to edit this approval.
          </template>
        </div>
        <mr-metadata
          aria-label$="[[fieldName]] Approval Metadata"
          approval-status="[[_status]]"
          approvers="[[approvers]]"
          setter="[[setter]]"
          field-defs="[[fieldDefs]]"
          is-approval="true"
        ></mr-metadata>
        <mr-inline-editor
          heading-level=4
          content="[[_survey.content]]"
          title$="[[fieldName]] Survey"
          edit-text="Edit responses"
          placeholder="Survey content and answer"
          on-save="_updateSurveyHandler"
        >
          <div class="survey">
            <mr-comment-content content="[[_survey.content]]"></mr-comment-content>
          </div>
        </mr-inline-editor>
        <h4 class="medium-heading">Approval comments / Changelog</h3>
        <mr-comments
          heading-level=5
          comments="[[_comments]]"
          edit-permission="editissueapproval"
        >
          <h4 id$="[[_editId]]" class="medium-heading">
            Editing approval: [[phaseName]] &gt; [[fieldName]]
          </h4>
          <mr-edit-metadata
            id="metadataForm"
            approvers="[[approvers]]"
            field-defs="[[fieldDefs]]"
            statuses="[[_availableStatuses]]"
            status="[[_status]]"
            has-approver-privileges="[[_hasApproverPrivileges]]"
            is-approval
            disabled="[[updatingApproval]]"
            error="[[updateApprovalError.description]]"
            on-save="save"
            on-discard="reset"
          ></mr-edit-metadata>
        </mr-comments>
      </iron-collapse>
    `;
  }

  static get is() {
    return 'mr-approval-card';
  }

  static get properties() {
    return {
      fieldName: String,
      approvers: Array,
      approvalComments: Array,
      phaseName: String,
      setter: Object,
      fieldDefs: {
        type: Array,
        computed:
          '_computeApprovalFieldDefs(fieldDefsByApprovalName, fieldName)',
      },
      fieldDefsByApprovalName: Object,
      user: Object,
      userGroups: Object,
      issue: {
        type: Object,
        observer: 'reset',
      },
      issueId: String,
      projectConfig: Object,
      projectName: String,
      class: {
        type: String,
        reflectToAttribute: true,
        computed: '_computeClass(_status)',
      },
      comments: Array,
      opened: {
        type: Boolean,
        reflectToAttribute: true,
        value: false,
      },
      statusEnum: {
        type: String,
        value: '',
      },
      statuses: {
        type: Array,
        value: () => {
          return Object.keys(STATUS_CLASS_MAP).map(
            (status) => (
              {status, docstring: STATUS_DOCSTRING_MAP[status], rank: 1}));
        },
      },
      updatingApproval: Boolean,
      updateApprovalError: Object,
      _availableStatuses: {
        type: Array,
        computed: '_filterStatuses(_status, statuses, _hasApproverPrivileges)',
      },
      _comments: {
        type: Array,
        computed: '_filterComments(comments, fieldName)',
      },
      _editId: {
        type: String,
        computed: '_computeEditId(fieldName)',
      },
      _survey: {
        type: String,
        computed: '_computeSurvey(comments, fieldName)',
      },
      _isApprovalOwner: {
        type: Boolean,
        computed: '_computeIsApprovalOwner(approvers, user.email, userGroups)',
        observer: '_openUserCards',
      },
      _hasApproverPrivileges: {
        type: Boolean,
        computed: `_computeHasApproverPrivileges(user.isSiteAdmin,
          _isApprovalOwner)`,
      },
      _expandIcon: {
        type: String,
        computed: '_computeExpandIcon(opened)',
      },
      _status: {
        type: String,
        computed: '_computeStatus(statusEnum)',
      },
      _statusIcon: {
        type: String,
        computed: '_computeStatusIcon(class)',
      },
    };
  }

  static mapStateToProps(state, element) {
    return {
      fieldDefsByApprovalName: selectors.fieldDefsByApprovalName(state),
      user: state.user,
      userGroups: state.userGroups,
      issue: state.issue,
      issueId: state.issueId,
      projectConfig: state.projectConfig,
      projectName: state.projectName,
      comments: state.comments,
      updatingApproval: state.updatingApproval,
      updateApprovalError: state.updateApprovalError,
    };
  }

  reset(issue) {
    if (!this.$.metadataForm) return;
    this.$.metadataForm.reset();
  }

  save() {
    const form = this.$.metadataForm;
    const data = form.getDelta();
    const sendEmail = form.sendEmail;
    const loads = form.loadAttachments();
    const delta = this._generateDelta(data);

    Promise.all(loads).then((uploads) => {
      if (data.comment || Object.keys(delta).length > 0 ||
          uploads.length > 0) {
        this._updateApproval({
          commentContent: data.comment,
          approvalDelta: delta,
          uploads: uploads,
          sendEmail: sendEmail,
        });
      }
    }).catch((reason) => {
      console.error('loading file for attachment: ', reason);
    });
  }

  _generateDelta(data) {
    let delta = {};

    if (data.status) {
      delta['status'] = TEXT_TO_STATUS_ENUM[data.status];
    }

    const approversAdded = data.approversAdded || [];
    const approversRemoved = data.approversRemoved || [];

    if (approversAdded.length > 0) {
      delta['approverRefsAdd'] = this._displayNamesToUserRefs(
        approversAdded);
    }

    if (approversRemoved.length > 0) {
      delta['approverRefsRemove'] = this._displayNamesToUserRefs(
        approversRemoved);
    }

    const fieldValuesAdded = data.fieldValuesAdded || [];
    const fieldValuesRemoved = data.fieldValuesRemoved || [];

    if (fieldValuesAdded.length) {
      delta['fieldValsAdd'] = data.fieldValuesAdded;
    }

    if (fieldValuesRemoved.length) {
      delta['fieldValsRemove'] = data.fieldValuesRemoved;
    }
    return delta;
  }

  _displayNamesToUserRefs(list) {
    return list.map((name) => ({'displayName': name}));
  }

  toggleCard(evt) {
    this.opened = !this.opened;
  }

  _updateApproval(messageBody) {
    if (!messageBody || !Object.keys(messageBody).length) return;
    const baseMessage = {
      issueRef: {
        projectName: this.projectName,
        localId: this.issueId,
      },
    };
    const message = Object.assign({
      fieldRef: {
        type: fieldTypes.APPROVAL_TYPE,
        fieldName: this.fieldName,
      },
    }, baseMessage, messageBody);

    this.dispatchAction({type: actionType.UPDATE_APPROVAL_START});

    window.prpcClient.call(
      'monorail.Issues', 'UpdateApproval', message
    ).then((resp) => {
      this.dispatchAction({
        type: actionType.UPDATE_APPROVAL_SUCCESS,
        approval: resp.approval,
      });
      actionCreator.fetchIssue(this.dispatchAction.bind(this), baseMessage);
      actionCreator.fetchComments(this.dispatchAction.bind(this), baseMessage);
    }, (error) => {
      this.dispatchAction({
        type: actionType.UPDATE_APPROVAL_FAILURE,
        error: error,
      });
    });
  }

  _computeClass(status) {
    return STATUS_CLASS_MAP[status];
  }

  _computeExpandIcon(opened) {
    if (opened) {
      return 'expand_less';
    }
    return 'expand_more';
  }

  _computeStatus(statusEnum) {
    return STATUS_ENUM_TO_TEXT[statusEnum || ''];
  }

  _computeStatusIcon(cl) {
    return CLASS_ICON_MAP[cl];
  }

  _computeIsApprovalOwner(approvers, userEmail, userGroups) {
    if (!userEmail || !approvers) return false;
    userGroups = userGroups || [];
    return !!approvers.find((a) => {
      return a.displayName === userEmail || userGroups.find(
        (group) => group.displayName === a.displayName
      );
    });
  }

  _computeHasApproverPrivileges(isSiteAdmin, isApprovalOwner) {
    return isSiteAdmin || isApprovalOwner;
  }

  // TODO(zhangtiff): Change data flow here so that this is only computed
  // once for all approvals.
  _filterComments(comments, fieldName) {
    if (!comments || !fieldName) return;
    return comments.filter((c) => (
      c.approvalRef && c.approvalRef.fieldName === fieldName
    )).splice(1);
  }

  _computeApprovalFieldDefs(fdMap, approvalName) {
    if (!fdMap) return [];
    return fdMap.get(approvalName) || [];
  }

  _computeEditId(fieldName) {
    return `edit${fieldName}`;
  }

  // TODO(zhangtiff): Change data flow here so that this is only computed
  // once for all approvals.
  _computeSurvey(comments, fieldName) {
    if (!comments || !fieldName) return;
    for (let i = comments.length - 1; i >= 0; i--) {
      if (comments[i].approvalRef
          && comments[i].approvalRef.fieldName === fieldName
          && comments[i].descriptionNum) {
        return comments[i];
      }
    }
    return {};
  }

  _filterStatuses(status, statuses, hasApproverPrivileges) {
    const currentStatusIsRestricted =
      APPROVER_RESTRICTED_STATUSES.has(status);
    return statuses.filter((s) => {
      const includeCurrentStatus = s.status === status;
      // These statuses should only be set by approvers.
      // Non-approvers can't change statuses when they're set to an
      // approvers-only status.
      if (!hasApproverPrivileges &&
          (APPROVER_RESTRICTED_STATUSES.has(s.status) ||
          currentStatusIsRestricted)
      ) {
        return includeCurrentStatus;
      }
      return includeCurrentStatus || s.status !== 'NotSet';
    });
  }

  _openUserCards(isApprovalOwner) {
    if (!this.opened && isApprovalOwner) {
      this.opened = true;
    }
  }

  _updateSurveyHandler(evt) {
    if (!evt || !evt.detail) return;
    this._updateApproval({
      commentContent: evt.detail.commentContent,
      isDescription: true,
      sendEmail: evt.detail.sendEmail,
    });
  }

  _toString(bool) {
    return bool.toString();
  }
}

customElements.define(MrApprovalCard.is, MrApprovalCard);
