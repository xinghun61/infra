'use strict';

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
      fields: {
        type: Array,
        statePath: 'issue.fieldValues',
      },
      token: {
        type: String,
        statePath: 'token',
      },
      user: {
        type: String,
        statePath: 'user',
      },
      issueId: {
        type: String,
        statePath: 'issueId',
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
            (status) => ({status, rank: 1}));
        },
      },
      _availableStatuses: {
        type: Array,
        computed: '_filterStatuses(_status, statuses, _isApprovalOwner)',
      },
      _comments: {
        type: Array,
        computed: '_filterComments(comments, fieldName)',
      },
      _survey: {
        type: String,
        computed: '_computeSurvey(comments, fieldName)',
      },
      _isApprovalOwner: {
        type: Boolean,
        computed: '_computeIsApprovalOwner(approvers, user)',
        observer: '_openUserCards',
      },
      _fieldList: {
        type: Array,
        computed: '_computeFieldList(fields, fieldName)',
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
      _onSubmitComment: {
        type: Function,
        value: function() {
          return this._submitCommentHandler.bind(this);
        },
      },
      _updateSurvey: {
        type: Function,
        value: function() {
          return this._updateSurveyHandler.bind(this);
        },
      },
    };
  }

  edit() {
    this.$.metadataForm.reset();
    this.$.editApproval.open();
  }

  cancel() {
    this.$.editApproval.close();
  }

  save() {
    const data = this.$.metadataForm.getData();
    const delta = {};

    if (data.status !== this._status) {
      delta['status'] = TEXT_TO_STATUS_ENUM[data.status];
    }

    // Map oldApprovers from userRef objects into raw display names to make
    // the array the same format as newApprovers.
    // TODO(zhangtiff): Figure out how to handle truncated display names.
    const oldApprovers = this.approvers.map((a) => (a.displayName));
    const newApprovers = data.approvers;

    const approverEquals = (a, b) => (a.toLowerCase() === b.toLowerCase());

    const approversAdd = fltHelpers.arrayDifference(newApprovers, oldApprovers,
      approverEquals);
    const approversRemove = fltHelpers.arrayDifference(oldApprovers,
      newApprovers, approverEquals);

    if (approversAdd.length > 0) {
      delta['approver_refs_add'] = this._displayNamesToUserRefs(approversAdd);
    }

    if (approversRemove.length > 0) {
      delta['approver_refs_remove'] = this._displayNamesToUserRefs(
        approversRemove);
    }

    if (data.comment || Object.keys(delta).length > 0) {
      this._updateApproval(data.comment, delta);
    }

    this.cancel();
  }

  _displayNamesToUserRefs(list) {
    return list.map((name) => ({'display_name': name}));
  }

  toggleCard(evt) {
    this.opened = !this.opened;
  }

  _submitCommentHandler(comment) {
    this._updateApproval(comment);
  }

  _updateApproval(commentData, delta, isDescription) {
    const baseMessage = {
      trace: {token: this.token},
      issue_ref: {
        project_name: this.projectName,
        local_id: this.issueId,
      },
    };
    const message = Object.assign({}, baseMessage, {
      field_ref: {
        type: 'APPROVAL_TYPE',
        field_name: this.fieldName,
      },
      comment_content: commentData || '',
    });

    if (delta) {
      message.approval_delta = delta;
    }

    if (isDescription) {
      message.is_description = true;
    }

    this.dispatch({type: actionType.UPDATE_APPROVAL_START});

    window.prpcClient.call(
      'monorail.Issues', 'UpdateApproval', message
    ).then((resp) => {
      this.dispatch({
        type: actionType.UPDATE_APPROVAL_SUCCESS,
        approval: resp.approval,
      });
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
      return 'expand-less';
    }
    return 'expand-more';
  }

  _computeStatus(statusEnum) {
    return STATUS_ENUM_TO_TEXT[statusEnum || ''];
  }

  _computeStatusIcon(cl) {
    return CLASS_ICON_MAP[cl];
  }

  _computeIsApprovalOwner(users, user) {
    if (!user || !users) return;
    return users.find((u) => {
      return u.displayName === user;
    });
  }

  // TODO(zhangtiff): Change data flow here so that this is only computed
  // once for all approvals.
  _filterComments(comments, fieldName) {
    if (!comments || !fieldName) return;
    return comments.filter((c) => (
      c.approvalRef && c.approvalRef.fieldName === fieldName
    )).splice(1);
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

  // TODO(zhangtiff): Change data flow here so that approvals are only
  // separated once then passed around later.
  _computeFieldList(fields, fieldName) {
    return computeFunction.computeFieldList(fields, fieldName);
  }

  _filterStatuses(status, statuses, isApprover) {
    return statuses.filter((s) => {
      // These statuses should only be set by approvers.
      if (!isApprover && ['NA', 'Approved', 'NotApproved'].includes(s.status)) {
        return false;
      }
      return s.status === status || s.status !== 'NotSet';
    });
  }

  _openUserCards(isApprovalOwner) {
    if (!this.opened && isApprovalOwner) {
      this.opened = true;
    }
  }

  _updateSurveyHandler(content) {
    this._updateApproval(content, null, true);
  }
}

customElements.define(MrApprovalCard.is, MrApprovalCard);
