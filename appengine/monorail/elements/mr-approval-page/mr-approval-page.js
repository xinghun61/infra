'use strict';

/**
 * `<mr-approval-page>` ....
 *
 * The main entry point for a given launch issue.
 *
 */
class MrApprovalPage extends Polymer.Element {
  static get is() {
    return 'mr-approval-page';
  }

  static get properties() {
    return {
      gates: {
        type: Array,
        value: [
          {
            gateName: 'Beta',
            approvals: [
              {
                title: 'Privacy',
                survey: `
                  Describe how this feature changes how any data is handled.
                  Everything changes

                  Are there any changes to how PII gets handled?
                  Yes
                `,
                comments: [
                  {
                    user: 'tpm@sample.com',
                    content: 'We should schedule a meeting with the privacy team ASAP.',
                  },
                  {
                    user: 'developer@sample.com',
                    content: 'We met offline, they\'ve approved this.',
                  },
                ],
                labels: [
                  {name: 'Status', values: ['Approved']},
                ],
                users: [
                  {
                    name: 'Approver(s)',
                    values: ['approver@chromium.org', 'privacy@chromium.org'],
                  },
                ],
              },
              {
                title: 'Security',
                survey: `
                  What are the possible risks?
                  Bad people could break stuff.

                  How are you preventing the risks
                  We are assuming all people are nice.
                `,
                comments: [
                  {user: 'tpm@sample.com', content: 'Please don\'t make such dangerous assumptions.'},
                  {user: 'developer@sample.com', content: 'Please have more faith in humanity.'},
                ],
                labels: [
                  {name: 'Status', values: ['Approved']},
                ],
                users: [
                  {name: 'Approver(s)', values: ['approver@chromium.org', 'approver-group@chromium.org']},
                ],
              },
              {
                title: 'Legal',
                survey: `
                  Please answer the questions listed in the LegalQuestions link above
                `,
                comments: [
                  {user: 'legal@sample.com', content: 'Thanks for answering the questions. We have started the Legal review process.'},
                ],
                urls: [
                  {name: 'LegalQuestions', values: ['go/legalquestionnaire']},
                ],
                labels: [
                  {name: 'Status', values: ['Approved']},
                ],
                users: [
                  {name: 'Approver(s)', values: ['chrome-lawyers@chromium.org']},
                ],
              },
            ],
          },
          {
            gateName: 'Stable Exp',
            approvals: [
              {
                title: 'Test',
                survey: `
                  Tell us how to test this
                  Execute the tests

                  Some question about Finch
                  No
                `,
                comments: [
                  {user: 'tpm@sample.com', content: 'These answers are unacceptable.'},
                  {user: 'developer@sample.com', content: 'My bad'},
                ],
                labels: [
                  {name: 'Status', values: ['Approved']},
                ],
                users: [
                  {name: 'Approver(s)', values: ['approver@chromium.org', 'approver-group@chromium.org']},
                ],
              },
              {
                title: 'UX',
                survey: `
                  What are you building?
                  Something amazing

                  Are we putting users first?
                  Yes, everything else is following
                `,
                comments: [
                  {user: 'daisy@sample.com', content: 'This is amazing! Wonderful idea.'},
                  {user: 'oldsport@sample.com', content: 'Your teams are doing incredible things!'},
                ],
                urls: [
                  {name: 'UI-FAQ', values: ['go/ui-review-faq']},
                  {name: 'Mocks', values: ['go/auto-fill-mocks']},
                ],
                labels: [
                  {name: 'Status', values: ['Approved']},
                ],
                users: [
                  {name: 'Approver(s)', values: ['approver@chromium.org', 'approver-group@chromium.org']},
                ],
              },
              {
                title: 'Accessibility',
                survey: `
                  List the UX changes you've made and the intended behavior of each component
                  Moved button below description section

                  Is there any information that is only indicated using color?
                  No, a status icon turns green or red but there also a text that states the current status.
                `,
                comments: [
                  {user: 'daisy@sample.com', content: 'This is amazing! Wonderful idea.'},
                  {user: 'oldsport@sample.com', content: 'Your teams are doing incredible things!'},
                ],
                urls: [
                  {name: 'Accessibility-screenreaders-faq', values: ['go/screenreaders-faq']},
                ],
                labels: [
                  {name: 'Status', values: ['Approved']},
                ],
                users: [
                  {name: 'Approver(s)', values: ['approver@chromium.org', 'approver-group@chromium.org']},
                ],
              },
              {
                title: 'Leadership',
                survey: `
                  Summarize this feature and how it impacts our users
                  TLDR: ....
                `,
                comments: [
                  {user: 'tpm@sample.com', content: 'Please take this seriously'},
                  {user: 'developer@sample.com', content: 'Absolutely not.'},
                ],
                urls: [],
                labels: [
                  {name: 'Status', values: ['Approved']},
                ],
                users: [
                  {name: 'Approver(s)', values: ['leadership@chromium.org']},
                ],
              },
            ],
          },
          {
            gateName: 'Stable',
            approvals: [
              {
                title: 'Leadership',
                survey: `
                  Are there any significant changes since Stable(1%)?
                  Who's to say
                `,
                comments: [
                  {user: 'tpm@sample.com', content: 'Please take this seriously'},
                  {user: 'developer@sample.com', content: 'Absolutely not.'},
                ],
                urls: [],
                labels: [
                  {name: 'Status', values: ['Approved']},
                ],
                users: [
                  {name: 'Approver(s)', values: ['leadesrship@chromium.org']},
                ],
              },
            ],
          },
        ],
      },
      currentGateIndex: Number,
    };
  }

  changeGate(gateIdx) {
    this.currentGateIndex = gateIdx;
  }

  _onGateSelected(e) {
    this.changeGate(e.detail.gateIndex);
  }
}

customElements.define(MrApprovalPage.is, MrApprovalPage);
