'use strict';

class MrDayIcon extends Polymer.Element {
  static get is() {
    return 'mr-day-icon';
  }

  static get properties() {
    return {
      activityLevel: {
        type: Number,
        reflectToAttribute: true,
      },
      commits: {
        type: Number,
      },
      comments: {
        type: Number,
      },
      date: {
        type: Number,
      },
      class: {
        type: String,
        reflectToAttribute: true,
        computed: '_computeClass(selected)',
      },
      selected: {
        type: Boolean,
        value: false,
      },
    };
  }

  _computeClass(selected) {
    return selected ? 'selected' : '';
  }
}
customElements.define(MrDayIcon.is, MrDayIcon);
