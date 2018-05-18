'use strict';

/**
 * `<mr-issue-details>`
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
            content: `
                5th test comment. I am a long comment who will be testing
                how long comments look. With a really long comment,
                you have to be careful to make sure the UI doesn't get
                stretched. After all, it would be disappointing if people had a
                perfectly good long comment but it caused problems by stretching
                the UI. How long do you think this comment should be?

                I will add some line breaks to make it taller without making it
                a lot longer in text.

                With the power of line breaks it's really easy to stretch the
                content on a page.

                I have a few points I want to make:

                1. Monorail

                2. Hello world.

                3. Three.

                4. This is a number

                Now that you've read my 4-point plan, I hope you this ramble
                has been information. Have a nice day! And thanks for checking
                out this FLT mock.
            `,
          },
        ],
      },
    };
  }
}
customElements.define(MrIssueDetails.is, MrIssueDetails);
