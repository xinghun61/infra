'use strict';

const LINE_SEPARATOR = /\r?\n/;

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
      surveyTemplate: String,
      editting: {
        type: Boolean,
        value: false,
      },
      _surveyLines: {
        type: Array,
        value: [],
        computed: '_computeSurveyLines(surveyTemplate, survey)',
      },
    };
  }

  edit() {
    this.editting = true;
  }

  cancel() {
    this.editting = false;
  }

  save() {
    this.survey = this.$.surveyContent.value;
    this.cancel();
  }

  _computeSurveyLines(template, survey) {
    let templateMap = {};
    template.trim().split(LINE_SEPARATOR).forEach((line) => {
      line = line.trim();
      templateMap[line] = true;
    });
    const surveyLines = survey.trim().split(LINE_SEPARATOR);
    return surveyLines.map((line) => {
      line = line.trim();
      let res = {text: line, bold: false};
      if (line in templateMap) {
        res.bold = true;
      }
      return res;
    });
  }
}

customElements.define(MrSurvey.is, MrSurvey);
