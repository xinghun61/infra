'use strict';

/**
 * `<mr-issue-header>`
 *
 * The header for a given launch issue.
 *
 */
class MrIssueHeader extends ReduxMixin(Polymer.Element) {
  static get is() {
    return 'mr-issue-header';
  }

  static get properties() {
    return {
      created: {
        type: Object,
        value: () => {
          return new Date();
        },
      },
      issue: {
        type: Object,
        value: {},
        statePath: 'issue',
      },
      reporter: {
        type: String,
        value: 'reporter@chromium.org',
      },
      you: String,
      _flipperCount: {
        type: Number,
        value: 20,
      },
      _flipperIndex: {
        type: Number,
        computed: '_computeFlipperIndex(issue.localId, _flipperCount)',
      },
      _nextId: {
        type: Number,
        computed: '_computeNextId(issue.localId)',
      },
      _prevId: {
        type: Number,
        computed: '_computePrevId(issue.localId)',
      },
    };
  }

  _computeFlipperIndex(i, count) {
    return i % count + 1;
  }

  _computeNextId(id) {
    return id + 1;
  }

  _computePrevId(id) {
    return id - 1;
  }
}

customElements.define(MrIssueHeader.is, MrIssueHeader);
