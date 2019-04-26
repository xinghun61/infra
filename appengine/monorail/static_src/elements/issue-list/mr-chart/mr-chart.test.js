import {assert} from 'chai';
import sinon from 'sinon';

import MrChart from 'elements/issue-list/mr-chart/mr-chart.js';
import AutoRefreshPrpcClient from 'prpc.js';

// TODO(jeffcarp): Export prefix from prpc-client and use that.
const xssiPrefix = ')]}\'';
let element;
let chartLoadedPromise;
let dataLoadedPromise;

const setupElement = () => {
  if (element && document.body.contains(element)) {
    // Avoid setting up multiple versions of the same element.
    document.body.removeChild(element);
    element = null;
  }
  const el = document.createElement('mr-chart');
  el.setAttribute('project-name', 'rutabaga');
  chartLoadedPromise = new Promise((resolve) => {
    el.addEventListener('chartLoaded', resolve);
  });
  dataLoadedPromise = new Promise((resolve) => {
    el.addEventListener('allDataLoaded', resolve);
  });

  document.body.appendChild(el);
  return el;
};

suite('mr-chart', () => {
  setup(() => {
    window.CS_env = {
      token: 'rutabaga-token',
      tokenExpiresSec: 0,
      app_version: 'rutabaga-version',
    };
    sinon.stub(AutoRefreshPrpcClient, 'isTokenExpired').callsFake(() => false);
    sinon.stub(window, 'fetch').callsFake(() => {
      return new Promise((resolve, reject) => {
        const dataStr = JSON.stringify({
          snapshotCount: [{count: 8}],
          unsupportedField: [],
          searchLimitReached: false,
        });
        const responseBody = new Blob([xssiPrefix + dataStr]);

        resolve(new Response(responseBody, {
          status: 201,
          headers: {
            'Content-type': 'application/json',
            'X-Prpc-Grpc-Code': 0,
          },
        }));
      });
    });

    // Stub RAF to execute immediately.
    sinon.stub(window, 'requestAnimationFrame').callsFake((func) => func());

    element = setupElement();
  });

  teardown(() => {
    document.body.removeChild(element);

    window.fetch.restore();
    window.requestAnimationFrame.restore();
    AutoRefreshPrpcClient.isTokenExpired.restore();
  });

  suite('constructor', () => {
    test('sets this.projectname', () => {
      assert.equal(element.projectName, 'rutabaga');
    });
  });

  suite('data loading', () => {
    setup(() => {
      // Stub search params.
      sinon.stub(MrChart, 'getSearchParams');
      const searchParams = new URLSearchParams();
      searchParams.set('q', 'owner:rutabaga@chromium.org');
      searchParams.set('can', '8');
      MrChart.getSearchParams.returns(searchParams);

      // Stub MrChart.makeTimestamps to return 6, not 30 data points.
      const originalMakeTimestamps = MrChart.makeTimestamps;
      sinon.stub(MrChart, 'makeTimestamps').callsFake((endDate) => {
        return originalMakeTimestamps(endDate, 6);
      });
      sinon.stub(MrChart, 'getEndDate').callsFake(() => {
        return new Date(Date.UTC(2018, 10, 3, 23, 59, 59));
      });

      // Re-instantiate element after stubs.
      element = setupElement();
    });

    teardown(() => {
      MrChart.getSearchParams.restore();
      MrChart.makeTimestamps.restore();
      MrChart.getEndDate.restore();
    });

    test('makes a series of XHR calls', async () => {
      await dataLoadedPromise;
      assert.deepEqual(element.values, [8, 8, 8, 8, 8, 8]);
    });

    test('sets indices and correctly re-orders values', async () => {
      await dataLoadedPromise;

      const timestampMap = new Map([
        [1540857599, 0], [1540943999, 1], [1541030399, 2], [1541116799, 3],
        [1541203199, 4], [1541289599, 5],
      ]);
      sinon.stub(MrChart.prototype, '_fetchDataAtTimestamp').callsFake(
        async (ts) => ({issues: timestampMap.get(ts)}));

      const endDate = new Date(Date.UTC(2018, 10, 3, 23, 59, 59));
      await element._fetchData(endDate);

      assert.deepEqual(element.indices, [
        '10/29/2018', '10/30/2018', '10/31/2018',
        '11/1/2018', '11/2/2018', '11/3/2018',
      ]);
      assert.deepEqual(element.values, [0, 1, 2, 3, 4, 5]);

      MrChart.prototype._fetchDataAtTimestamp.restore();
    });

    test('if issue count is null, defaults to 0', async () => {
      window.fetch.restore();
      sinon.stub(window, 'fetch').callsFake(() => {
        return new Promise((resolve, reject) => {
          const dataStr = JSON.stringify({
            snapshotCount: [{}],
          });
          const responseBody = new Blob([xssiPrefix + dataStr]);
          resolve(new Response(responseBody, {
            status: 201,
            headers: {
              'Content-type': 'application/json',
              'X-Prpc-Grpc-Code': 0,
            },
          }));
        });
      });
      MrChart.makeTimestamps.restore();
      sinon.stub(MrChart, 'makeTimestamps').callsFake((endDate) => {
        return [1234567, 2345678, 3456789];
      });

      element = setupElement();
      await new Promise((resolve) => {
        element.addEventListener('allDataLoaded', resolve);
      });

      await element._fetchData(new Date());
      assert.deepEqual(element.values, [0, 0, 0]);
    });
  });

  suite('end date change detection', () => {
    setup(async () => {
      await chartLoadedPromise;

      sinon.spy(window.history, 'pushState');
      sinon.spy(element, '_fetchData');
    });

    teardown(() => {
      element._fetchData.restore();
      window.history.pushState.restore();
    });

    test('changes URL param when end_date input changes', async () => {
      element.endDateInput.value = '2017-10-02';
      const event = new Event('change');
      element.endDateInput.dispatchEvent(event);

      sinon.assert.calledOnce(history.pushState);
      sinon.assert.calledWith(history.pushState, {}, '',
        sinon.match('end_date=2017-10-02'));

      sinon.assert.calledOnce(element._fetchData);
      const endDate = new Date(Date.UTC(2017, 9, 2, 23, 59, 59));
      sinon.assert.calledWith(element._fetchData, endDate);
    });
  });

  suite('progress bar', () => {
    setup(async () => {
      await chartLoadedPromise;
    });

    test('visible based on loading progress', async () => {
      assert.equal(element.progressBar.style.visibility, 'visible');
      assert.equal(element.progressBar.value, 0.05);
      assert.isTrue(element.endDateInput.disabled);

      const endDate = new Date(Date.UTC(2018, 10, 3, 23, 59, 59));
      await element._fetchData(endDate);

      assert.equal(element.progressBar.style.visibility, 'hidden');
      assert.equal(element.progressBar.value, 1);
      assert.isFalse(element.endDateInput.disabled);

      const endDate2 = new Date(Date.UTC(2018, 5, 3, 23, 59, 59));
      const fetchDataPromise = element._fetchData(endDate2);

      // Values are reset on second call.
      assert.equal(element.progressBar.style.visibility, 'visible');
      assert.equal(element.progressBar.value, 0.05);
      assert.isTrue(element.endDateInput.disabled);

      await fetchDataPromise;

      assert.equal(element.progressBar.style.visibility, 'hidden');
      assert.equal(element.progressBar.value, 1);
      assert.isFalse(element.endDateInput.disabled);
    });
  });


  suite('static methods', () => {
    suite('sortInBisectOrder', () => {
      test('orders first, last, median recursively', () => {
        assert.deepEqual(MrChart.sortInBisectOrder([]), []);
        assert.deepEqual(MrChart.sortInBisectOrder([9]), [9]);
        assert.deepEqual(MrChart.sortInBisectOrder([8, 9]), [8, 9]);
        assert.deepEqual(MrChart.sortInBisectOrder([7, 8, 9]), [7, 9, 8]);
        assert.deepEqual(
          MrChart.sortInBisectOrder([1, 2, 3, 4, 5]), [1, 5, 3, 2, 4]);
      });
    });

    suite('makeTimestamps', () => {
      test('throws an error if endDate not passed', () => {
        assert.throws(() => {
          MrChart.makeTimestamps();
        }, 'endDate required');
      });
      test('returns an array of in seconds', () => {
        const endDate = new Date(Date.UTC(2018, 10, 3, 23, 59, 59));
        const secondsInDay = 24 * 60 * 60;

        assert.deepEqual(MrChart.makeTimestamps(endDate, 6), [
          1541289599 - (secondsInDay * 5), 1541289599 - (secondsInDay * 4),
          1541289599 - (secondsInDay * 3), 1541289599 - (secondsInDay * 2),
          1541289599 - (secondsInDay * 1), 1541289599 - (secondsInDay * 0),
        ]);
      });
    });

    suite('dateStringToDate', () => {
      test('returns null if no input', () => {
        assert.isNull(MrChart.dateStringToDate());
      });

      test('returns a new Date at EOD UTC', () => {
        const actualDate = MrChart.dateStringToDate('2018-11-03');
        const expectedDate = new Date(Date.UTC(2018, 10, 3, 23, 59, 59));
        assert.equal(expectedDate.getTime(), 1541289599000, 'Sanity check.');

        assert.equal(actualDate.getTime(), expectedDate.getTime());
      });
    });

    suite('getSearchParams', () => {
      test('returns URLSearchParams', () => {
        const urlParams = new URLSearchParams(location.search.substring(1));
        urlParams.set('eat', 'rutabagas');
        const newUrl = `${location.protocol}//${location.host}${location.pathname}?${urlParams.toString()}`;
        window.history.pushState({}, '', newUrl);

        const actualParams = MrChart.getSearchParams();
        assert.equal(actualParams.get('eat'), 'rutabagas');
      });
    });

    suite('getEndDate', () => {
      let clock;

      setup(() => {
        sinon.stub(MrChart, 'getSearchParams');
        clock = sinon.useFakeTimers(10000);
      });

      teardown(() => {
        clock.restore();
        MrChart.getSearchParams.restore();
      });

      test('returns end date if in URL params', () => {
        const searchParams = new URLSearchParams();
        searchParams.set('end_date', '2018-11-03');
        MrChart.getSearchParams.returns(searchParams);

        const expectedDate = new Date(Date.UTC(2018, 10, 3, 23, 59, 59));
        // Time sanity check.
        assert.equal(Math.round(expectedDate.getTime() / 1e3), 1541289599);

        const actual = MrChart.getEndDate();
        assert.equal(actual.getTime(), expectedDate.getTime());
      });

      test('returns EOD of current date if not in URL params', () => {
        MrChart.getSearchParams.returns(new URLSearchParams());

        const expectedDate = new Date();
        expectedDate.setHours(23);
        expectedDate.setMinutes(59);
        expectedDate.setSeconds(59);

        assert.equal(MrChart.getEndDate().getTime(), expectedDate.getTime());
      });

      test('returns EOD of URL param is empty', () => {
        const searchParams = new URLSearchParams();
        searchParams.set('end_date', '');
        MrChart.getSearchParams.returns(searchParams);

        const expectedDate = new Date();
        expectedDate.setHours(23);
        expectedDate.setMinutes(59);
        expectedDate.setSeconds(59);

        assert.equal(MrChart.getEndDate().getTime(), expectedDate.getTime());
      });
    });

    suite('makeIndices', () => {
      test('returns dates in mm/dd/yyy format', () => {
        const timestamps = [
          1540857599, 1540943999, 1541030399,
          1541116799, 1541203199, 1541289599,
        ];
        assert.deepEqual(MrChart.makeIndices(timestamps), [
          '10/29/2018', '10/30/2018', '10/31/2018',
          '11/1/2018', '11/2/2018', '11/3/2018',
        ]);
      });
    });
  });
});