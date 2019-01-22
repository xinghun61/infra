'use strict';

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
class MrApprovalCard extends ReduxMixin(Polymer.Element) {
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
      fieldDefsByApprovalName: {
        type: Object,
        statePath: selectors.fieldDefsByApprovalName,
      },
      user: {
        type: Object,
        statePath: 'user',
      },
      userGroups: {
        type: Array,
        statePath: 'userGroups',
      },
      issue: {
        type: Object,
        statePath: 'issue',
        observer: 'reset',
      },
      issueId: {
        type: String,
        statePath: 'issueId',
      },
      projectConfig: {
        type: Object,
        statePath: 'projectConfig',
      },
      projectName: {
        type: String,
        statePath: 'projectName',
      },
      class: {
        type: String,
        reflectToAttribute: true,
        computed: '_computeClass(_status)',
      },
      comments: {
        type: Array,
        statePath: 'comments',
      },
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
      updatingApproval: {
        type: Boolean,
        statePath: 'updatingApproval',
      },
      updateApprovalError: {
        type: Object,
        statePath: 'updateApprovalError',
      },
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
      _updateSurvey: {
        type: Function,
        value: function() {
          return this._updateSurveyHandler.bind(this);
        },
      },
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

    this.dispatch({type: actionType.UPDATE_APPROVAL_START});

    window.prpcCall(
      'monorail.Issues', 'UpdateApproval', message
    ).then((resp) => {
      this.dispatch({
        type: actionType.UPDATE_APPROVAL_SUCCESS,
        approval: resp.approval,
      });
      actionCreator.fetchIssue(this.dispatch.bind(this), baseMessage);
      actionCreator.fetchComments(this.dispatch.bind(this), baseMessage);
    }, (error) => {
      this.dispatch({
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

  _updateSurveyHandler(content, sendEmail) {
    this._updateApproval({
      commentContent: content,
      isDescription: true,
      sendEmail: sendEmail,
    });
  }

  _toString(bool) {
    return bool.toString();
  }
}

customElements.define(MrApprovalCard.is, MrApprovalCard);
