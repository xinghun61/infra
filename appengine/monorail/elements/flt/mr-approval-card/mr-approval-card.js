'use strict';

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
class MrApprovalCard extends Polymer.Element {
  static get is() {
    return 'mr-approval-card';
  }

  static get properties() {
    return {
      title: String,
      approvalComments: Array,
      gateName: String,
      survey: String,
      surveyTemplate: String,
      urls: Array,
      labels: Array,
      users: Array,
      user: String,
      class: {
        type: String,
        reflectToAttribute: true,
        computed: '_computeClass(_status)',
      },
      opened: {
        type: Boolean,
        reflectToAttribute: true,
        value: false,
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
      _isApprovalOwner: {
        type: Boolean,
        computed: '_computeIsApprovalOwner(users, user)',
        observer: '_openUserCards',
      },
      _expandIcon: {
        type: String,
        computed: '_computeExpandIcon(opened)',
      },
      _status: {
        type: String,
        computed: '_computeStatus(labels)',
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

  _computeStatus(labels) {
    let status = labels.find((l) => (l.name === 'Status'));
    return status.values[0];
  }

  _computeStatusIcon(cl) {
    return CLASS_ICON_MAP[cl];
  }

  _computeIsApprovalOwner(users, user) {
    const approvers = users.find((u) => {
      return u.name == 'Approvers';
    });
    return approvers.values.includes(user);
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
