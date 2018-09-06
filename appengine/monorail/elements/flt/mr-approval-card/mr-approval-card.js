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
      fieldValues: {
        type: Array,
        statePath: 'issue.fieldValues',
      },
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
        type: String,
        statePath: 'user',
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
    const data = this.$.metadataForm.getDelta();
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

    if (data.comment || Object.keys(delta).length > 0) {
      this._updateApproval(data.comment, delta);
    }

    this.cancel();
  }

  _displayNamesToUserRefs(list) {
    return list.map((name) => ({'displayName': name}));
  }

  toggleCard(evt) {
    this.opened = !this.opened;
  }

  _submitCommentHandler(comment) {
    this._updateApproval(comment);
  }

  _updateApproval(commentData, delta, isDescription) {
    const baseMessage = {
      issueRef: {
        projectName: this.projectName,
        localId: this.issueId,
      },
    };
    const message = Object.assign({}, baseMessage, {
      fieldRef: {
        type: fieldTypes.APPROVAL_TYPE,
        fieldName: this.fieldName,
      },
      commentContent: commentData || '',
    });

    message.approvalDelta = delta || {};

    if (isDescription) {
      message.isDescription = true;
    }

    this.dispatch({type: actionType.UPDATE_APPROVAL_START});

    window.prpcClient.call(
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

  _computeApprovalFieldDefs(fdMap, approvalName) {
    if (!fdMap) return [];
    return fdMap.get(approvalName) || [];
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
