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
      _revs: {
        type: Array,
        value: null,
      },
    };
  }

  ready() {
    super.ready();
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
      if (range.host.indexOf('https://') == 0) {
        range.host = range.host.substr('https://'.length);
      }
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
