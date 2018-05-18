'use strict';

const PRIORITY_REGEX = /priority-(.+)/i;

/**
 * `<mr-metadata>`
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
      links: {
        type: Array,
        value: [{name: 'DesignDoc', values: ['go/design-doc']}],
      },
      labels: {
        type: Array,
        value: ['Priority-1', 'Test-Label', 'Launch-ASAP-Please'],
      },
      blockedOn: {
        type: Array,
        value: [1234, 31434, 43434],
      },
      blocking: {
        type: Array,
        value: [4321, 41555, 99999],
      },
      components: {
        type: Array,
        value: ['Test>Component'],
      },
      status: {
        type: String,
        value: 'Assigned',
      },
      users: {
        type: Array,
        value: [
          {name: 'Reporter', values: ['reporter@chromium.org']},
          {name: 'Owner', values: ['owner@chromium.org']},
          {name: 'TL', values: ['techlead@chromium.org']},
          {name: 'PM', values: ['pm@chromium.org']},
          {
            name: 'CC',
            values: [
              'user1@chromium.rog',
              'otheruser@chromium.org',
              'otheruserwithlongeremail@chromium.org',
            ],
          },
        ],
      },
      _priority: {
        type: String,
        computed: '_computePriority(labels)',
      },
      _labelsList: {
        type: Array,
        computed: '_computeLabelsList(labels)',
      },
    };
  }

  _computePriority(labels) {
    for (let i = 0; i < labels.length; i++) {
      let match = labels[i].match(PRIORITY_REGEX);
      if (match !== null && match.length > 1) {
        return match[1];
      }
    }
    return '-';
  }

  _computeLabelsList(labels) {
    return labels.filter((l) => (!PRIORITY_REGEX.test(l)));
  }
}

customElements.define(MrMetadata.is, MrMetadata);
