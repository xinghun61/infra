'use strict';

const HOST_URL_RE = /([a-z0-9]+(\-[a-z0-9]+)*)\.googlesource\.com/gi;
const HOST_NAME_GROUP = 1;
const CHROMIUM_HOST = 'chromium';
const CHROMIUM_REPO = 'chromium.src';

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
    let startRev = '0';
    let endRev = '0';
    let startPos = '0';
    let endPos = '0';
    let host;
    let repo;
    let url;
    // Note: For now, if the range.host is NOT empty, we can assume the range
    // data was filled using builds' inputs in buildbucket_analyzer.go. Range
    // data from build inputs have reliable host/repo values but do not have
    // commit positions data, so start and end are revision numbers instead.
    // An empty range host means range data was NOT filled using builds'
    // inputs, and therefore, do not have reliable repo and revision values.
    // So commit positions are used as start and end values instead and we can
    // assume these ranges are for chromium builds.
    if (this.range.host && this.range.host.length > 0) {
      let matches;
      while ((matches = HOST_URL_RE.exec(this.range.host)) !== null) {
        host = matches[HOST_NAME_GROUP];
      }
      // We cannot add '/' to a param value in the url, so we replace them
      // with '.' and the backend will parse and add '/'s back.
      repo = this.range.repo.replace('/', '.');
      startRev = this._regressionRevStart(this.range);
      endRev = this._regressionRevEnd(this.range);
      url = `/api/v1/revrange/${host}/${repo}` +
        `?startRev=${startRev}&endRev=${endRev}`;
    } else {
      host = CHROMIUM_HOST;
      repo = CHROMIUM_REPO;
      startPos = this._regressionStart(this.range);
      endPos = this._regressionEnd(this.range);
      url = `/api/v1/revrange/${host}/${repo}` +
        `?startPos=${startPos}&endPos=${endPos}`;
    }
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

  _shouldUseRangeRevisions(range) {
    // Note: If range.host is not empty, it means range data was
    // filled using builds' inputs. Build inputs have unreliable
    // commit positions but reliable revisions, so revisions
    // should be used instead of positions.
    return (range.host && range.host.length > 0 &&
            range.revisions && range.revisions.length > 0);
  }

  _regressionRange(range) {
    if (!range) {
      return '';
    }

    let start = '';
    let end;
    if (this._shouldUseRangeRevisions(range)) {
      // Note: revisions should not be sorted. We can assume
      // revisions are in the correct order.

      // Get the first 7 characters of start and end revisions
      // as user friendly revision numbers for display.
      start = this._regressionRevStart(range).substring(0, 7);
      end = this._regressionRevEnd(range).substring(0, 7);
    } else {
      range.positions.sort();
      start = this._regressionStart(range);
      end = this._regressionEnd(range);
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
    if (this._shouldUseRangeRevisions(range)) {
      const start = range.revisions[0];
      const revLength = range.revisions.length;
      const end = range.revisions[revLength - 1];
      return `https://${range.host}/${range.repo}/+log/${start}^..${end}`;
    } else if (range.positions && range.positions.length > 0) {
      // _checkUseRangeRevisions determined that range.revisions
      // are unreliable because build outputs data was used to populate
      // ranges data. Build outputs are only used for chromium builds so
      // we can send the start and end positions to test-results to
      // produce a chromium/src link.
      range.positions.sort();
      let end = this._parseCommitPosition(range.positions[0]);
      const start = end;
      if (range.positions.length > 1) {
        end = this._parseCommitPosition(
          range.positions[range.positions.length - 1]);
      }
      return 'https://test-results.appspot.com/revision_range?start=' +
          `${start}&end=${end}`;
    }
    return '';
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
