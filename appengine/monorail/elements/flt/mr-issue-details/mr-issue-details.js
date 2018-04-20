'use strict';

/**
 * `<mr-issue-details>` ....
 *
 * This is the main details section for a given issue.
 *
 */
class MrIssueDetails extends Polymer.Element {
  static get is() {
    return 'mr-issue-details';
  }

  // TODO(zhangtiff): Replace this with real data.
  static get properties() {
    return {
      summary: {
        type: String,
        value: 'Autofill credit card icons',
      },
      description: {
        type: String,
        value: `More detailed description of what this feature is. Lorem ipsum
                dolor sit amet, consectetur adipiscing elit Pellentesque nec
                vulputate enim. Vestibulum vitae tempor elementum. ivamus vitae
                libero vitae nisl hendrerit iaculis sit amet nec lacus. Mauris
                ornare nec nunc id posuere.`,
      },
      comments: {
        type: Array,
        value: [
          {
            user: 'testuser@chromium.org',
            content: '1. Lorem ipsum dolor sit amet, consectetur adipiscing elit',
          }, {
            user: 'testuser@chromium.org',
            content: '2. Pellentesque nec vulputate enim. Vestibulum vitae tempor.',
          }, {
            user: 'testuser@chromium.org',
            content: '3. ivamus vitae libero vitae nisl hendrerit iaculis sit amet.',
          }, {
            user: 'testuser@chromium.org',
            content: '4. Mauris ornare nec nunc id posuere.',
          }, {
            user: 'testuser@chromium.org',
            content: '5th test comment.',
          },
        ],
      },
      strings: {
        type: Array,
        value: [{name: 'RandomString', values: ['useful string']}],
      },
    };
  }

  editData() {
    this.$.editDialog.open();
  }
}
customElements.define(MrIssueDetails.is, MrIssueDetails);
