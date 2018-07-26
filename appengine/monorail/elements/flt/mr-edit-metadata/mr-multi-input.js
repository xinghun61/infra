'use strict';

/**
 * `<mr-multi-input>`
 *
 * Input form for inputing fields with multiple values. For now this is
 * barebones, but we can make it fancier later.
 *
 */
// TODO(zhangtiff): Add autocomplete.
// TODO(zhangtiff): Consider whether we want to use chips for this input.
class MrMultiInput extends Polymer.Element {
  static get is() {
    return 'mr-multi-input';
  }

  static get properties() {
    return {
      // By default, there's no max. Set this to 1 to make this a single input.
      // TODO(zhangtiff): Add validation for going over the max.
      max: {
        type: Number,
        value: 0,
      },
      // Values is a one way mapping. Do not add expect values to represent the
      // current data in the form element.
      values: {
        type: Array,
        value: [],
      },
      _defaultValue: {
        type: String,
        computed: '_joinValues(values)',
      },
    };
  }

  focus() {
    this.$.multiInput.focus();
  }

  reset() {
    this.$.multiInput.value = this._defaultValue;
  }

  getValue() {
    let valueList = this.$.multiInput.value.split(',');
    valueList = valueList.map((s) => (s.trim()));
    valueList = valueList.filter((s) => (s.length > 0));
    if (this.max && valueList.length > this.max) {
      // TODO(zhangtiff): Handle this case in a more user friendly way.
      console.error('Input has more values than max.');
      valueList = valueList.slice(0, this.max);
    }
    return valueList;
  }

  _joinValues(arr) {
    return arr.join(',');
  }
}

customElements.define(MrMultiInput.is, MrMultiInput);
