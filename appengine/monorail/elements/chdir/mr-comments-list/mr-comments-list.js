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
      displayedComments: {
        type: Array,
        computed: '_computedComments(selectedDate, comments)',
        value: [],
      },
      viewedUserId: {
        type: Number,
      },
      comments: {
        type: Array,
        notify: true,
        value: [],
      },
      selectedDate: {
        type: Number,
        notify: true,
      },
    };
  }

  _truncateMessage(message) {
    return message && message.substring(0, message.indexOf('\n'));
  }

  _computedComments(selectedDate, comments) {
    if (selectedDate == undefined) {
      return comments;
    } else {
      let computedComments = [];
      if (comments == undefined) {
        return computedComments;
      }
      for (let i = 0; i < comments.length; i++) {
        if (comments[i].timestamp <= selectedDate &&
           comments[i].timestamp >= (selectedDate - 86400)) {
          computedComments.push(comments[i]);
        }
      }
      return computedComments;
    }
  }

  _checkIfCommentsEmpty(displayedComments) {
    return !displayedComments || displayedComments.length === 0;
  }
}
customElements.define(MrCommentList.is, MrCommentList);
