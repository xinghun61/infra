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
        notify: true,
        value: [],
      },
      displayedCommits: {
        type: Array,
        computed: '_computedCommits(selectedDate, commits)',
        value: [],
      },
      commitsLoaded: {
        type: Boolean,
      },
      fetchingCommits: {
        type: Boolean,
      },
      user: {
        type: String,
      },
      selectedDate: {
        type: Number,
        notify: true,
      },
      emptyList: {
        type: Boolean,
        computed: '_checkIfCommitsEmpty(displayedCommits)',
      },
    };
  }

  _computedCommits(selectedDate, commits) {
    if (selectedDate == undefined) {
      return commits;
    } else {
      let computedCommits = [];
      if (commits == undefined) {
        return computedCommits;
      }
      for (let i = 0; i < commits.length; i++) {
        if (commits[i].commitTime <= selectedDate &&
           commits[i].commitTime >= (selectedDate - 86400)) {
          computedCommits.push(commits[i]);
        }
      }
      return computedCommits;
    }
  }

  _checkEmptyList(list) {
    if (list.length != 0) {
      return list;
    } else {
      return ['None'];
    }
  }

  _truncateSHA(sha) {
    return sha.substring(0, 6);
  }

  _checkIfCommitsEmpty(displayedCommits) {
    return !displayedCommits || displayedCommits.length === 0;
  }

  _truncateRepo(repo) {
    let url = repo.substring(8, repo.length - 1);
    let myProject = url.substring(0, url.indexOf('.'));

    let myDirectory = url.substring(url.indexOf('/') + 1, url.length);
    let myRepo = myProject + ' ' + myDirectory;
    return myRepo;
  }

  _truncateMessage(message) {
    return message.substring(0, message.indexOf('\n'));
  }
}
customElements.define(MrCommitTable.is, MrCommitTable);
