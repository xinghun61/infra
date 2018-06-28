'use strict';

/**
 * `<mr-survey>`
 *
 * This element shows a card for a single approval.
 *
 */
class MrSurvey extends Polymer.Element {
  static get is() {
    return 'mr-survey';
  }

  static get properties() {
    return {
      survey: String,
      editing: {
        type: Boolean,
        value: false,
      },
    };
  }

  edit() {
    this.editing = true;
  }

  cancel() {
    this.editing = false;
  }

  save() {
    this.survey = this.$.surveyContent.value;
    this.cancel();
  }
}

customElements.define(MrSurvey.is, MrSurvey);
