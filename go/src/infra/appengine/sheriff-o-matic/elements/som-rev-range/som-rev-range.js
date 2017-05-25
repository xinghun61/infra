(function() {
  'use strict';

  Polymer({
    is: 'som-rev-range',

    properties: {
      range: {type: Object, value: null},
      _collapseMessage: {
        type: String,
        value: 'more',
      },
      _revs: {type: Array, value: null},
      _iconName: {type: String, value: 'icons:unfold-more'},
    },

    ready: function() { this._fetchData(); },

    _fetchData: function() {
      let start = this._regressionStart(this.range);
      let end = this._regressionEnd(this.range);
      let url = `/api/v1/revrange/${start}/${end}`;
      this.$.loadingMessage.hidden = false;
      fetch(url).then(
          (resp) => {
            resp.text().then(
                (bodyJson) => {
                  // remove the )]}' on the first line.
                  bodyJson = bodyJson.substr(')]}\'\n'.length);
                  let body = JSON.parse(bodyJson);
                  this._revs = body.log;
                  this.$.loadingMessage.hidden = true;
                },
                (reject) => { console.error(reject); });
          },
          (reject) => { console.error(reject); });
    },

    _toggleCollapse: function() {
      this.$.collapse.toggle();
      this._iconName =
          this.$.collapse.opened ? 'icons:unfold-less' : 'icons:unfold-more';
      this._collapseMessage = this.$.collapse.opened ? 'less' : 'more';
    },

    _shortHash: function(hash) { return hash.substring(0, 8); },

    _firstLine: function(message) { return message.split('\n')[0]; },

    _regressionStart: function(range) {
      if (!range || (!range.positions || range.positions.length == 0)) {
        return '';
      }

      return this._parseCommitPosition(range.positions[0]);
    },

    _regressionEnd: function(range) {
      if (!range || (!range.positions || range.positions.length == 0)) {
        return '';
      }

      return this._parseCommitPosition(
          range.positions[range.positions.length - 1]);
    },

    _regressionRange: function(range) {
      if (!range) {
        return '';
      }

      let start = this._regressionStart(range);
      let end = this._regressionEnd(range);

      if (start && end) {
        return `${start} - ${end}`;
      }

      return start;
    },

    _regressionRangeLink: function(range) {
      if (!range || !range.positions) {
        return '';
      }
      let end = this._parseCommitPosition(range.positions[0]);
      let start = end;
      if (range.positions.length > 1) {
        end = this._parseCommitPosition(
            range.positions[range.positions.length - 1]);
      }
      return 'https://test-results.appspot.com/revision_range?start=' +
             `${start}&end=${end}`;
    },

    _parseCommitPosition: function(pos) {
      let groups = /refs\/heads\/master@{#([0-9]+)}/.exec(pos);
      if (groups && groups.length == 2) {
        return groups[1];
      }
    },

    _isSuspect: function(rev, range) {
      if (range && range.revisions_with_results) {
        for (var i in range.revisions_with_results) {
          let cl = range.revisions_with_results[i];
          if (cl.revision == rev.commit && cl.is_suspect) {
            return true;
          }
        }
      }
      return false;
    },

    _calulateClass: function(rev, range) {
      if (this._isSuspect(rev, range)) {
        return 'suspect-cl';
      }
      return '';
    },
  });
})();
