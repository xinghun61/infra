(function() {
  'use strict';

  Polymer({
    is: 'som-edit-expectation-form',

    properties: {
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
          'Rebaseline',
          'Slow',
          'Skip',
          'Timeout',
          'WontFix',
          'Missing',
          'NeedsRebaseline',
          'NeedsManualRebaseline',
        ],
      },
      modifierValues: {
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
          'Linux32',
          'Precise',
          'Trusty',
          'Android',
          'Release',
          'Debug',
        ],
      },
    },

    expectationChanged: function(evt) {
      // Make a copy of the expectation to edit in this form. Modify only
      // the copy, so we can cancel, or fire an edited event with old
      // and new values set in the details.
      this._editValue = JSON.parse(JSON.stringify(this.expectation));
    },

    _addBug: function(evt) {
      this.push('_editValue.Bugs', this.$.newBug.value);
      this.$.newBug.value = '';
    },

    _expects: function(item, val) {
      if (!item || !item.Expectations) {
        return false;
      }
      let ret = item.Expectations.some((v) => { return v == val; });
      return ret;
    },

    _removeBug: function(evt) {
      this.arrayDelete('_editValue.Bugs', evt.target.value);
    },

    _toggleExpectation: function(evt) {
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
    },

    _hasModifier: function(item, val) {
      if (!item || !item.Modifiers) {
        return false;
      }
      let ret = item.Modifiers.some((v) => { return v == val; });
      return ret;
    },

    _toggleModifier: function(evt) {
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
    },

    _createChangeCL: function(evt) {
      this.fire('create-change-cl', {
          oldValue: this.expectation,
          newValue: this._editValue,
      });
    },

    _cancelChangeCL: function(evt) {
      // Reset form fields to the original values.
      this.expectationChanged();
      this.fire('cancel-change-cl');
    },

  });
})();
