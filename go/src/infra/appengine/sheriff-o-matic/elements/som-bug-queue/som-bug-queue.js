(function() {
  'use strict';

  Polymer({
    is: 'som-bug-queue',

    properties: {
      bugQueueLabel: {
        type: String,
        observer: '_changeBugQueueLabel',
      },
      _assignedBugsJson: {
        type: Object,
        value: null,
      },
      _assignedBugsJsonError: {
        type: Object,
        value: null,
      },
      bugs: {
        type: Array,
        notify: true,
        computed: '_computeBugs(_bugQueueJson, _assignedBugsJson)',
      },
      _bugQueueJson: {
        type: Object,
        value: null,
      },
      _bugQueueJsonError: {
        type: Object,
        value: null,
      },
      _bugsLoaded: {
        type: Boolean,
        value: false,
      },
      _hideBugQueue: {
        type: Boolean,
        value: true,
        computed: '_computeHideBugQueue(bugQueueLabel)',
      },
      _isTrooperQueue: {
        type: Boolean,
        value: false,
        computed: '_computeIsTrooperQueue(bugQueueLabel)',
      },
      _showNoBugs: {
        type: Boolean,
        value: false,
        computed: '_computeShowNoBugs(bugs, _bugsLoaded, _bugQueueJsonError)',
      },
    },

    refresh: function() {
      if (this._hideBugQueue) {
        return;
      }

      let promises = [this.$.bugQueueAjax.generateRequest().completes];
      if (this._isTrooperQueue) {
        promises.push(this.$.assignedBugsAjax.generateRequest().completes);
      }

      Promise.all(promises).then((reponse) => {
        this._bugsLoaded = true;
      });
    },

    _computeBugs: function(bugQueueJson, assignedBugsJson) {
      let hasBugJson = bugQueueJson && bugQueueJson.items;
      let hasAssignedJson = assignedBugsJson && assignedBugsJson.items;
      if (!hasBugJson && !hasAssignedJson) {
        return [];
      } else if (!hasAssignedJson) {
        return bugQueueJson.items;
      } else if (!hasBugJson) {
        return assignedBugsJson.items;
      }
      return bugQueueJson.items.concat(assignedBugsJson.items);
    },

    _computeHideBugQueue: function(bugQueueLabel) {
      // No loading or empty message is shown unless a bug queue exists.
      return !bugQueueLabel || bugQueueLabel === '' ||
          bugQueueLabel === 'Performance-Sheriff-BotHealth';
    },

    _computeIsTrooperQueue: function(bugQueueLabel) {
      return bugQueueLabel === 'infra-troopers';
    },

    _computePriority: function(bug) {
      if (!bug || !bug.labels) {
        return '';
      }
      for (let i in bug.labels) {
        let match = bug.labels[i].match(/^Pri-(\d)$/);
        if (match) {
          let result = parseInt(match[1]);
          return result !== NaN ? result : '';
        }
      }
      return '';
    },

    _computeShowNoBugs: function(bugs, bugsLoaded, error) {
      // Show the "No bugs" message only when the queue is done loading
      return bugsLoaded && this._haveNoBugs(bugs) && this._haveNoErrors(error);
    },

    _changeBugQueueLabel: function() {
      this._bugQueueJson = null;
      this._bugQueueJsonError = null;

      this._assignedBugsJson = null;
      this._assignedBugsJsonError = null;

      this._bugsLoaded = false;

      this.refresh();
    },

    _filterBugLabels: function(labels, bugQueueLabel) {
      if (!labels) {
        return [];
      }
      return labels.filter((label) => {
        return label.toLowerCase() != bugQueueLabel.toLowerCase() &&
            !label.match(/^Pri-(\d)$/);
      });
    },

    _hasPriority: function(bug) {
      return this._computePriority(bug) !== '';
    },

    _haveNoBugs: function(bugs) {
      return !bugs || bugs.length == 0;
    },

    _haveNoErrors: function(error) {
      return !error;
    },

    _showBugsLoading: function(bugsLoaded, error) {
      return !bugsLoaded && this._haveNoErrors(error);
    },

    _sortBugs: function(bugs) {
      if (bugs) {
        // Sort bugs by priority.
        bugs.sort((a, b) => {
          let pA = this._computePriority(a);
          let pB = this._computePriority(b);
          if (pA === '' && pB === '') {
            return 0;
          } else if (pA === '') {
            // Put blank priority bugs after all other bugs.
            return 1;
          } else if (pB === '') {
            return -1;
          }
          return pA - pB;
        });
      }
      return bugs;
    }
  });
})();
