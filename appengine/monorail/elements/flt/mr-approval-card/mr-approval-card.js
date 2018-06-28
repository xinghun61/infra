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
      title: String,
      approvers: Array,
      approvalComments: Array,
      phaseName: String,
      setter: Object,
      fields: {
        type: Array,
        statePath: 'issue.fieldValues',
      },
      user: {
        type: String,
        statePath: 'user',
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
          return Object.keys(STATUS_CLASS_MAP);
        },
      },
      _availableStatuses: {
        type: Array,
        computed: '_filterStatuses(_status, statuses, _isApprovalOwner)',
      },
      _comments: {
        type: Array,
        computed: '_filterComments(comments, title)',
      },
      _survey: {
        type: String,
        computed: '_computeSurvey(comments, title)',
      },
      _isApprovalOwner: {
        type: Boolean,
        computed: '_computeIsApprovalOwner(approvers, user)',
        observer: '_openUserCards',
      },
      _fields: {
        type: Array,
        computed: '_filterFields(fields, title)',
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

  edit() {
    this.$.editApproval.open();
  }

  cancel() {
    this.$.editApproval.close();
  }

  save() {
    const data = this.$.metadataForm.getData();
    let newLabels = Object.assign([], this.labels);
    newLabels.forEach((l) => {
      if (l.name === 'Status') {
        l.values = [data.status];
      }
    });
    this.labels = newLabels;
    this.users = data.users;
    this.urls = data.urls;

    this.cancel();
  }

  toggleCard(evt) {
    this.opened = !this.opened;
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
  _filterComments(comments, title) {
    if (!comments || !title) return;
    return comments.filter((c) => (
      !c.descriptionNum && c.approvalRef && c.approvalRef.fieldName === title)
    );
  }

  // TODO(zhangtiff): Change data flow here so that this is only computed
  // once for all approvals.
  _computeSurvey(comments, title) {
    if (!comments || !title) return;
    return comments.find((c) => (
      c.descriptionNum > 0 && c.approvalRef && c.approvalRef.fieldName === title
    ));
  }

  // TODO(zhangtiff): Change data flow here so that approvals are only
  // separated once then passed around later.
  _filterFields(fields, title) {
    if (!fields) return;
    return fields.filter((f) => {
      return f.fieldRef.approvalName === title;
    });
  }

  _filterStatuses(status, statuses, isApprover) {
    return statuses.filter((s) => {
      // These statuses should only be set by approvers.
      if (!isApprover && ['NA', 'Approved', 'NotApproved'].includes(s)) {
        return false;
      }
      return s === status || s !== 'NotSet';
    });
  }

  _openUserCards(isApprovalOwner) {
    if (!this.opened && isApprovalOwner) {
      this.opened = true;
    }
  }
}

customElements.define(MrApprovalCard.is, MrApprovalCard);
