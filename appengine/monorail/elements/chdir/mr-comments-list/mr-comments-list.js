'use strict';
/**
 * `<mr-comments-list>`
 *
 * The list of comments for a Monorail Polymer profile.
 *
 */
class MrCommentList extends Polymer.Element {
  static get is() {
    return 'mr-comments-list';
  }

  static get properties() {
    return {
      user: {
        type: String,
      },
      viewedUserId: {
        type: Number,
        observer: '_listActitivities',
      },
      token: String,
    }
  }

  _listActitivities (userId) {
    const message = {
      trace: {
        token: this.token,
      },
      user_ref: {
        user_id: userId,
      },
    };

    const listActivities = window.prpcClient.call(
      'monorail.Issues', 'ListActivities', message
    );

    listActivities.then(
      (resp) => {this.comments = resp.comments;},
      (error) => {}
    );
  }
}
customElements.define(MrCommentList.is, MrCommentList)
