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
        computed: 'computeActivityLevel(changes, bugs)',
      },
      changes: {
        type: Number,
        value: 0,
      },
      class: {
        type: String,
        reflectToAttribute: true,
        computed: '_computeClass(selected)',
      },
      bugs: {
        type: Number,
        value: 0,
      },
      selected: {
        type: Boolean,
        value: false,
      },
    };
  }

  computeActivityLevel(cls, bugs) {
    const activityNum = cls + bugs;
    if (activityNum >= 7) {
      // High.
      return 3;
    } else if (activityNum >= 3) {
      // Medium.
      return 2;
    } else if (activityNum > 0) {
      // Low.
      return 1;
    }
    // None
    return 0;
  }

  _computeClass(selected) {
    return selected ? 'selected' : '';
  }
}
customElements.define(MrDayIcon.is, MrDayIcon);
