'use strict';

/**
 * `<mr-metadata>` ....
 *
 * The metadata view for a single issue. Contains information such as the owner.
 *
 */
class MrMetadata extends Polymer.Element {
  static get is() {
    return 'mr-metadata';
  }

  static get properties() {
    return {
      id: {
        type: Number,
        value: 1111,
      },
      labels: {
        type: Array,
        value: [
          {
            name: 'M-Target',
            values: ['66-Dev', '66-Beta', '66-Stable'],
          },
          {
            name: 'M-Approved',
            values: ['66-Dev'],
          },
        ],
      },
      links: {
        type: Array,
        value: [{name: 'DesignDoc', values: ['go/design-doc']}],
      },
      users: {
        type: Array,
        value: [
          {name: 'TL', values: ['techlead@chromium.org']},
          {name: 'PM', values: ['pm@chromium.org']},
          {
            name: 'CC',
            values: ['user1@chromium.rog', 'otheruser@chromium.org'],
          },
        ],
      },
    };
  }
}

customElements.define(MrMetadata.is, MrMetadata);
