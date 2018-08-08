'use strict';

/**
 * `<mr-commit-table>`
 *
 * Table that displays user's commit history.
 *
 */
class MrCommitTable extends Polymer.Element {
  static get is() {
    return 'mr-commit-table';
  }

  static get properties() {
    return {
      commits: {
        type: Array,
      },
      displayedCommits: {
        type: Array,
      },
      commitsLoaded: {
        type: Boolean,
      },
      fetchingCommits: {
        type: Boolean,
      },
      token: {
        type: String,
      },
      user: {
        type: String,
        observer: '_getCommits',
      },
    };
  }

  _getCommits(user) {
    const d = new Date();
    const n = d.getTime();
    let currentTime = n / 1000;
    currentTime = Math.ceil(currentTime);
    let fromTime = currentTime - 31536000;

    const message = {
      trace: {token: this.token},
      email: user,
      from_timestamp: fromTime,
      until_timestamp: currentTime,
    };

    const getCommits = window.prpcClient.call(
      'monorail.Users', 'GetUserCommits', message
    );

    getCommits.then((resp) => {
      this.commits = resp.userCommits;
    }, (error) => {
    });
  }

  _truncateSHA(sha) {
    return sha.substring(0,6);
  }

  _truncateRepo(repo) {
    var url = repo.substring(8,repo.length-1);
    var myProject = url.substring(0,
      url.indexOf("."));

    var myDirectory = url.substring(url.indexOf("/")+1, url.length);
    var myRepo = myProject + " " + myDirectory;
    return myRepo;
  }

  _truncateMessage(message) {
    return message.substring(0, message.indexOf("\n"));
  }

}
customElements.define(MrCommitTable.is, MrCommitTable);
