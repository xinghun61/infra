'use strict';

/**
 * `<mr-profile-page>`
 *
 * The main entry point for a Monorail Polymer profile.
 *
 */
class MrProfilePage extends Polymer.Element {
  static get is() {
    return 'mr-profile-page';
  }

  static get properties() {
    return {
      user: {
        type: String,
        observer: '_getUserData',
      },
      logoutUrl: String,
      loginUrl: String,
      viewedUser: String,
      viewedUserId: Number,
      token: String,
      tokenExpiresSec: Number,
      lastVisitStr: String,
      starredUsers: Array,
      commits: {
        type: Array,
      },
      comments: {
        type: Array,
      },
      selectedDate: {
        type: Number,
      },
      _hideActivityTracker: {
        type: Boolean,
        computed: '_computeHideActivityTracker(user, viewedUser)',
      },
    };
  }

  _checkStarredUsers(list) {
    if (list.length != 0) {
      return list;
    } else {
      return ['None'];
    }
  }

  _getUserData() {
    const d = new Date();
    const n = d.getTime();
    let currentTime = n / 1000;
    currentTime = Math.ceil(currentTime);
    let fromTime = currentTime - 31536000;

    const commitMessage = {
      email: this.viewedUser,
      fromTimestamp: fromTime,
      untilTimestamp: currentTime,
    };

    const getCommits = window.__prpc.call(
      'monorail.Users', 'GetUserCommits', commitMessage, this.token,
      this.tokenExpiresSec
    );

    getCommits.then((resp) => {
      this.commits = resp.userCommits;
    }, (error) => {
    });

    const commentMessage = {
      userRef: {
        userId: this.viewedUserId,
      },
    };

    const listActivities = window.__prpc.call(
      'monorail.Issues', 'ListActivities', commentMessage, this.token,
      this.tokenExpiresSec
    );

    listActivities.then(
      (resp) => {
        this.comments = resp.comments;
      },
      (error) => {}
    );
  }

  _computeHideActivityTracker(user, viewedUser) {
    return user !== viewedUser;
  }
}

customElements.define(MrProfilePage.is, MrProfilePage);
