'use strict';

const FAKE_SUMMARIES = [
  'This is a test launch issue',
  'Autofill credit card icons',
  `Launch Chrome with this really long feature name that could be a lot longer
   except that there will probably be some sort of limit on how long someone can
   make a feature summary`,
  'Chrome Feature',
];

/**
 * `<mr-issue-header>`
 *
 * The header for a given launch issue.
 *
 */
class MrIssueHeader extends Polymer.Element {
  static get is() {
    return 'mr-issue-header';
  }

  static get properties() {
    return {
      issueId: Number,
      summary: {
        type: String,
        value: 'Autofill credit card icons',
        computed: '_mockSummary(issueId)',
      },
      you: String,
      _flipperCount: {
        type: Number,
        value: 20,
      },
      _flipperIndex: {
        type: Number,
        computed: '_computeFlipperIndex(issueId, _flipperCount)',
      },
      _nextId: {
        type: Number,
        computed: '_computeNextId(issueId)',
      },
      _prevId: {
        type: Number,
        computed: '_computePrevId(issueId)',
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

  _mockSummary(id) {
    return FAKE_SUMMARIES[id % FAKE_SUMMARIES.length];
  }
}

customElements.define(MrIssueHeader.is, MrIssueHeader);
