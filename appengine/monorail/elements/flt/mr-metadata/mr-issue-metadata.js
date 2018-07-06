'use strict';

/**
 * `<mr-issue-metadata>`
 *
 * The metadata view for a single issue. Contains information such as the owner.
 *
 */
class MrIssueMetadata extends ReduxMixin(Polymer.Element) {
  static get is() {
    return 'mr-issue-metadata';
  }

  static get properties() {
    return {
      issue: {
        type: Object,
        statePath: 'issue',
      },
      // TODO(zhangtiff): Get real data from jsonfeed API.
      statuses: {
        type: Array,
        value: [
          'Unconfirmed',
          'Untriaged',
          'Available',
          'Assigned',
          'Started',
        ],
      },
      _fields: {
        type: Array,
        computed: '_filterFields(issue.fieldValues)',
      },
    };
  }

  edit() {
    this.$.editMetadata.open();
  }

  cancel() {
    this.$.metadataForm.reset();
    this.$.editMetadata.close();
  }

  _filterFields(fields) {
    if (!fields) return [];
    return fields.filter((f) => {
      return !f.fieldRef.approvalName;
    });
  }
}

customElements.define(MrIssueMetadata.is, MrIssueMetadata);
