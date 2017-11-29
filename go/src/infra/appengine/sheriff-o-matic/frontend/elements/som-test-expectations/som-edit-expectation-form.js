'use strict';

class SomEditExpectationForm extends Polymer.LegacyElementMixin(Polymer.Element) {

  static get is() {
    return 'som-edit-expectation-form';
  }

  static get properties() {
    return {
      expectation: {
        type: Object,
        value: null,
        observer: 'expectationChanged',
      },
      _editValue: {
        type: Object,
        value: function() { return {}; },
        notify: true,
      },
      expectationValues: {
        type: Array,
        value: [
          'Crash',
          'Failure',
          'Pass',
          'Slow',
          'Skip',
          'Timeout',
          'NeedsManualRebaseline',
        ],
      },
      modifierValues: {
        // Note: these values are defined in
        // third_party/WebKit/Tools/Scripts/webkitpy/layout_tests/models/test_expectations.py
        type: Array,
        value: [
          'Mac',
          'Mac10.9',
          'Mac10.10',
          'Mac10.11',
          'Mac10.12',
          'Retina',
          'Win',
          'Win7',
          'Win10',
          'Linux',
          'Android',
          'KitKat',
          'Release',
          'Debug',
        ],
      },
    };
  }

  expectationChanged(evt) {
    if (!this.expectation) {
      return;
    }
    // Make a copy of the expectation to edit in this form. Modify only
    // the copy, so we can cancel, or fire an edited event with old
    // and new values set in the details.
    this._editValue = JSON.parse(JSON.stringify(this.expectation));
  }

  _addBug(evt) {
    this._newBugError = '';
    let bug = this.$.newBug.value;
    let parser = document.createElement('a');
    parser.href = bug;
    if (!bug.startsWith('https://')) {
      parser.href = 'https://' + bug;
    }
    if (isNaN(parseInt(bug)) && parser.hostname != 'bugs.chromium.org' &&
      parser.hostname != 'crbug.com') {
      this._newBugError = 'Invalid bug';
      return
    }

    this.push('_editValue.Bugs', this.$.newBug.value);
    this.$.newBug.value = '';
  }

  _expects(item, val) {
    if (!item || !item.Expectations) {
      return false;
    }
    let ret = item.Expectations.some((v) => { return v == val; });
    return ret;
  }

  _removeBug(evt) {
    this.arrayDelete('_editValue.Bugs', evt.target.value);
  }

  _toggleExpectation(evt) {
    if (!this._editValue.Expectations) {
      this._editValue.Expectations = [evt.target.value];
      return;
    }

    let pos = this._editValue.Expectations.indexOf(evt.target.value);
    if (pos == -1) {
      this._editValue.Expectations.push(evt.target.value);
      return;
    }

    this._editValue.Expectations =
        this._editValue.Expectations.filter((v, i) => { return pos != i; });
  }

  _hasModifier(item, val) {
    if (!item || !item.Modifiers) {
      return false;
    }
    let ret = item.Modifiers.some((v) => { return v == val; });
    return ret;
  }

  _toggleModifier(evt) {
    if (!this._editValue.Modifiers) {
      this._editValue.Modifiers = [evt.target.value];
      return;
    }

    let pos = this._editValue.Modifiers.indexOf(evt.target.value);
    if (pos == -1) {
      this._editValue.Modifiers.push(evt.target.value);
      return;
    }

    this._editValue.Modifiers =
        this._editValue.Modifiers.filter((v, i) => { return pos != i; });
  }

  _createChangeCL(evt) {
    this.fire('create-change-cl', {
        oldValue: this.expectation,
        newValue: this._editValue,
    });
  }

  _cancelChangeCL(evt) {
    // Reset form fields to the original values.
    this.expectationChanged();
    this.fire('cancel-change-cl');
  }
}

customElements.define(SomEditExpectationForm.is, SomEditExpectationForm);
