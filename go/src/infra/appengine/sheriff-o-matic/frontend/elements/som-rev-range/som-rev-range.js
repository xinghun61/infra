'use strict';

class SomRevRange extends Polymer.Element {

  static get is() {
    return 'som-rev-range';
  }

  static get properties() {
    return {
      range: {
        type: Object,
        value: null,
      },
      _collapseMessage: {
        type: String,
        value: 'more',
      },
      _errorCollapseMessage: {
        type: String,
        value: 'more',
      },
      _revs: {
        type: Array,
        value: null,
      },
      _iconName: {
        type: String,
        value: 'icons:unfold-more',
      },
    };
  }

  ready() {
    super.ready();

    this._fetchData();
  }

  _fetchData() {
    if (this.range && this.range.positions) {
      this.range.positions.sort();
    }
    // TODO(jojwang): use this._regressionRevStart/End
    // to send regression revisions instead of commit positions
    // to the backend.
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
              (reject) => {
                console.error(reject);
              });
        },
        (reject) => {
          console.error(reject);
        });
  }

  _toggleCollapse() {
    this.$.collapse.toggle();
    this._iconName =
        this.$.collapse.opened ? 'icons:unfold-less' : 'icons:unfold-more';
    this._collapseMessage = this.$.collapse.opened ? 'less' : 'more';
  }

  _toggleErrorCollapse() {
    let elem = Polymer.dom(this.root).querySelector('#errorCollapse');
    elem.toggle();
    this._errorCollapseMessage = elem.opened ? 'less' : 'more';
  }

  _shortHash(hash) {
    return hash.substring(0, 8);
  }

  _firstLine(message) {
    return message.split('\n')[0];
  }

  _regressionRevStart(range) {
    if (!range || (!range.revisions || range.revisions.length == 0)) {
      return '';
    }
    return range.revisions[0];
  }

  _regressionRevEnd(range) {
    if (!range || (!range.revisions || range.revisions.length == 0)) {
      return '';
    }
    return range.revisions[range.revisions.length - 1];
  }

  _regressionStart(range) {
    if (!range || (!range.positions || range.positions.length == 0)) {
      return '';
    }

    return this._parseCommitPosition(range.positions[0]);
  }

  _regressionEnd(range) {
    if (!range || (!range.positions || range.positions.length == 0)) {
      return '';
    }

    return this._parseCommitPosition(
        range.positions[range.positions.length - 1]);
  }

  _regressionRange(range) {
    if (!range) {
      return '';
    }

    let start = '';
    let end;
    if (range.positions && range.positions.length > 0) {
      range.positions.sort();
      start = this._regressionStart(range);
      end = this._regressionEnd(range);
    } else if (range.revisions && range.revisions.length > 0) {
      // Note: revisions should not be sorted. We can assume
      // revisions are in the correct order.

      // Get the first 7 characters of start and end revisions
      // as user friendly revision numbers for display.
      start = this._regressionRevStart(range).substring(0, 7);
      end = this._regressionRevEnd(range).substring(0, 7);
    }
    if (start && end) {
      return `${start} - ${end}`;
    }
    return start;
  }

  _regressionRangeLink(range) {
    if (!range) {
      return '';
    }
    // Note: A range with revisions instead of positions means
    // range data was gathered from builds' input gitilescommit.
    // gitilescommit contains host, repo and revisions, but no commit
    // positions.
    // Range data gathered from builds' outputs only reliably
    // have commit positions. And only chromium data are gathered from
    // build outputs. So for now, if range contains positions, we assume
    // they are for chromium builds and we use test-results to produce
    // the git url given the commit positions.
    if (!range.positions || range.positions.length == 0) {
      if (!range.revisions || range.revisions.length == 0) {
        return '';
      }
      const start = range.revisions[0];
      const revLength = range.revisions.length;
      const end = range.revisions[revLength - 1];
      return `${range.host}/${range.repo}/+log/${start}^..${end}`;
    }
    range.positions.sort();
    let end = this._parseCommitPosition(range.positions[0]);
    let start = end;
    if (range.positions.length > 1) {
      end = this._parseCommitPosition(
          range.positions[range.positions.length - 1]);
    }
    return 'https://test-results.appspot.com/revision_range?start=' +
           `${start}&end=${end}`;
  }

  _parseCommitPosition(pos) {
    let groups = /refs\/heads\/master@{#([0-9]+)}/.exec(pos);
    if (groups && groups.length == 2) {
      return groups[1];
    }
  }

  _isSuspect(rev, range) {
    if (range && range.revisions_with_results) {
      for (var i in range.revisions_with_results) {
        let cl = range.revisions_with_results[i];
        if (cl.revision == rev.commit && cl.is_suspect) {
          return true;
        }
      }
    }
    return false;
  }

  _calulateClass(rev, range) {
    if (this._isSuspect(rev, range)) {
      return 'suspect-cl';
    }
    return '';
  }

  _haveError(range) {
    return !!range && !!range.error;
  }
}

customElements.define(SomRevRange.is, SomRevRange);
