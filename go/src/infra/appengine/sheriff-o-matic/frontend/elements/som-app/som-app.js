(function() {
  'use strict';

  Polymer({
    is: 'som-app',
    properties: {
      alertsTimes: Object,
      _examinedAlertKey: {
        type: String,
        computed: '_computeExaminedAlertKey(_pathParts)',
      },
      _logdiffAlertKey: {
        type: String,
        computed: '_computeLogDiffKey(_pathParts)',
      },
      _fetchingAlerts: Boolean,
      _lastUpdated: {
        type: Object,
        computed: '_computeLastUpdated(alertsTimes.*)',
        value: null,
      },
      logoutUrl: String,
      _path: String,
      _pathIdentifier: {
        type: String,
        computed: '_computePathIdentifier(_pathParts)',
      },
      _pathParts: {
        type: Array,
        computed: '_computePathParts(_path)',
      },
      _selectedPage: {
        type: String,
        computed: '_computeSelectedPage(_pathIdentifier, _tree)',
      },
      _showAlertView: {
        type: Boolean,
        value: false,
        computed: '_computeShowAlertView(_selectedPage)',
      },
      _showRotationCalendar: {
        type: Boolean,
        value: false,
        computed: '_computeShowRotationCalendar(_selectedPage)',
      },
      _showTestExpectations: {
        type: Boolean,
        value: false,
        computed: '_computeShowTestExpectations(_selectedPage)',
      },
      _showTreeStatus: {
        type: Boolean,
        value: false,
        computed: '_computeShowTreeStatus(_selectedPage)',
      },
      _tree: {
        type: Object,
        computed: '_computeTree(_pathIdentifier, _trees)',
        value: function() {
          return {};
        },
      },
      _trees: {
        type: Object,
        computed: '_computeTrees(treesJson)',
      },
      treesJson: String,
      _treeLogo: {
        type: String,
        computed: '_computeTreeLogo(_tree)',
      },
      _staticPages: {
        type: Object,
        value: {
          'help-som': {
            pageId: 'helpSOM',
            displayText: 'How to Use',
          },
          'calendar': {
            pageId: 'rotationCalendar',
            displayText: 'Rotation Calendar',
          },
          'test-expectations': {
            pageId: 'testExpectations',
            displayText: 'Layout Test Expectations',
          },
          'status': {
            pageId: 'treeStatus',
            displayText: 'Tree Statuses',
          },
        },
      },
      user: String,
      collapseByDefault: Boolean,
      linkStyle: String,
    },

    _refresh: function() {
      let alertView = this.$$('som-alert-view');
      if (alertView) {
        alertView.refresh();
      }
    },

    _computeExaminedAlertKey: function(pathParts) {
      if (pathParts.length < 3) {
        return '';
      }
      if (pathParts[2] == 'examine') {
        if (pathParts.length > 3) {
          // Let som-examine element deal with the rest of the path.
          return window.unescape(pathParts.slice(3).join('/'));
        }
      }

      return '';
    },

    _computeLogDiffKey: function(pathParts) {
      if(pathParts.length!=7) {
        return '';
      }
      if(pathParts[2] == 'logdiff') {
        return window.unescape(pathParts.slice(3).join('/'));
      }
      return '';
    },

    _computeLastUpdated: function(alertsTimes) {
      alertsTimes = alertsTimes.base;

      // Alert streams are assumed to be always older than right now.
      let oldestDate = new Date();
      Object.keys(alertsTimes).forEach((tree) => {
        if (alertsTimes[tree] < oldestDate) {
          oldestDate = alertsTimes[tree];
        }
      });

      // Assume it takes less than 1 millisecond to calculate that.
      if (Date.now() - oldestDate > 1) {
        let date = moment(oldestDate * 1000).tz('America/Los_Angeles');
        return {
          'time': date.format('M/DD/YYYY, h:mm a z'),
          'relativeTime': date.fromNow()
        };
      }
      return null;
    },

    _computeTree: function(pathIdentifier, trees) {
      if (pathIdentifier in trees) {
        return trees[pathIdentifier];
      }
      return null;
    },

    _computeTreeLogo: function(tree) {
      if (tree) {
        return `/logos/${tree.name}`;
      }
      return null;
    },

    _computeTrees: function(json) {
      let treeList = JSON.parse(json);
      let trees = {};
      if (!treeList) {
        return trees;
      }
      treeList.forEach(function(tree) {
        trees[tree.name] = tree;
      });
      return trees;
    },

    _computePathIdentifier: function(pathParts) {
      if (!pathParts || pathParts.length < 2)
        return '';
      return pathParts[1];
    },

    _computePathParts: function(path) {
      let pathParts = path.split('/');
      if (pathParts.length < 2) {
        console.error('error: pathParts < 2', pathParts);
      }
      return pathParts;
    },

    _computeSelectedPage: function(pathIdentifier, tree) {
      if (pathIdentifier in this._staticPages) {
        return this._staticPages[pathIdentifier].pageId;
      } else if (tree) {
        // On the page for a tree.
        return 'alertView';
      }
      // Default page
      return 'helpSOM';
    },

    _computeShowAlertView: function(selectedPage) {
      return selectedPage == 'alertView';
    },

    _computeShowRotationCalendar: function(selectedPage) {
      return selectedPage == 'rotationCalendar';
    },

    _computeShowTestExpectations: function(selectedPage) {
      return selectedPage == 'testExpectations';
    },

    _computeShowTreeStatus: function(selectedPage) {
      return selectedPage == 'treeStatus';
    },
  });
})();
