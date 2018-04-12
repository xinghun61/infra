'use strict';

/**
 * `<mr-approval-card>` ....
 *
 * This element shows a card for a single approval.
 *
 */
class MrApprovalCard extends Polymer.Element {
  static get is() {
    return 'mr-approval-card';
  }

  ready() {
    super.ready();
  }

  static get properties() {
    return {
      teamTitle: String,
      approvalComments: Array,
      survey: String,
      urls: Array,
      labels: Array,
      users: Array,
      _surveyLines: {
        type: Array,
        value: [],
        computed: '_computeSurveyLines(survey)',
      },
    };
  }

  editData() {
    this.$.editDialog.open();
  }

  toggleCard(evt) {
    let path = evt.path;
    if (path.some((el) => el.classList && el.classList.contains('no-toggle'))) {
      return;
    }
    this.$.cardCollapse.toggle();
  }

  _computeSurveyLines(survey) {
    return survey.trim().split(/\r?\n/);
  }
}
customElements.define(MrApprovalCard.is, MrApprovalCard);
