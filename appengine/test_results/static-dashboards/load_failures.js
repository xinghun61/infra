// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

var loadfailures = loadfailures || {};

(function() {

loadfailures._testTypeIndex = 0;
loadfailures._failureData = {};
loadfailures._loader = null;

// FIXME: This is a gross hack to make it so that changing the test type in loadNextTestType doesn't reload the page.
history.reloadRequiringParameters = history.reloadRequiringParameters.filter(function(item) { return item != 'testType' });

loadfailures.loadNextTestType = function(historyInstance)
{
    if (loadfailures._loader) {
        var testType = builders.testTypes[loadfailures._testTypeIndex];
        var failures = loadfailures._loader.builderKeysThatFailedToLoad();
        if (failures.length) {
            var failingBuilders = [];
            failures.forEach(function(builderKey) {
                failingBuilders.push(builders.builderFromKey(builderKey));
            });
            loadfailures._failureData.failingBuilders[testType] = failingBuilders;
        }

        var stale = loadfailures._loader.staleBuilderKeys();
        if (stale.length) {
            var staleBuilders = [];
            stale.forEach(function(builderKey) {
                staleBuilders.push(builders.builderFromKey(builderKey));
            });
            loadfailures._failureData.staleBuilders[testType] = staleBuilders;
        }

        if ((failures.length || stale.length) && !Object.keys(g_resultsByBuilder).length)
            loadfailures._failureData.testTypesWithNoSuccessfullLoads.push(testType);
    }

    loadfailures._testTypeIndex++;
    if (loadfailures._testTypeIndex == builders.testTypes.length) {
        loadfailures._testTypeIndex = 0;
        loadfailures._generatePage();
        return;
    }

    if (!loadfailures._failureData) {
        loadfailures._failureData = {
            failingBuilders: {},
            staleBuilders: {},
            testTypesWithNoSuccessfullLoads: [],
            builderToMaster: {},
        }
    }
    historyInstance.crossDashboardState.testType = builders.testTypes[loadfailures._testTypeIndex];

    var totalIterations = builders.testTypes.length;
    var currentIteration = builders.testTypes.length + loadfailures._testTypeIndex;
    $('content').innerHTML = 'Loading ' + currentIteration + '/' + totalIterations + ' ' +
        historyInstance.crossDashboardState.testType + '...';

    // FIXME: Gross hack to allow loading all the builders for different test types.
    // Change loader.js to allow you to pass in the state that it fills instead of setting globals.
    g_resultsByBuilder = {};
    loadfailures._loader = new loader.Loader()
    loadfailures._loader.load();
}

loadfailures._generatePage = function()
{
    $('content').innerHTML = loadfailures._html(loadfailures._failureData);
}

loadfailures._htmlForBuilder = function(builder, testType)
{
    return '<tr class="builder">' +
        '<td>' + builder.key() +
        '<td><a href="http://test-results.appspot.com/testfile?testtype=' +
            testType + '&builder=' + builder.builderName + '&master=' + builder.masterName + '">uploaded results</a>' +
        '<td><a href="' + builder.master().builderPath(builder.builderName) + '">buildbot</a>' +
    '</tr>';
}

loadfailures._html = function(failureData)
{
    var html = '';

    var failingBuildersByTestType = failureData.failingBuilders;
    var staleBuildersByTestType = failureData.staleBuilders;
    var testTypesWithNoSuccessfullLoads = failureData.testTypesWithNoSuccessfullLoads;

    var testTypes = testTypesWithNoSuccessfullLoads.concat(Object.keys(failingBuildersByTestType).concat(Object.keys(staleBuildersByTestType)));
    var uniqueTestTypes = testTypes.sort().filter(function(value, index, array) {
        return array.indexOf(value) === index;
    });

    if (!uniqueTestTypes.length)
        return;

    html += '<table><tr><th>Test type</th><th>>1 week stale</th><th>>1 day stale, <1 week stale</th></tr>';

    uniqueTestTypes.forEach(function(testType) {
        var failures = failingBuildersByTestType[testType] || [];
        var failureHtml = '';
        failures.sort().forEach(function(builder) {
            failureHtml += loadfailures._htmlForBuilder(builder, testType);
        });

        var stale = staleBuildersByTestType[testType] || [];
        var staleHtml = '';
        stale.sort().forEach(function(builder) {
            staleHtml += loadfailures._htmlForBuilder(builder, testType);
        });

        var noBuildersHtml = testTypesWithNoSuccessfullLoads.indexOf(testType) != -1 ? '<b>No builders with up to date results.</b>' : '';

        html += '<tr>' +
            '<td><a href="http://test-results.appspot.com/testfile?name=results.json&testtype=' + testType + '" target=_blank>' +
                testType +
            '</a></td>' +
            '<td>' + noBuildersHtml + '<table>' + failureHtml + '</table></td>' +
            '<td><table>' + staleHtml + '</table></td>' +
        '</tr>';
    });
    html += '</table>';

    return html;
}

// FIXME: Once dashboard_base, loader and ui stop using the g_history global, we can stop setting it here.
g_history = new history.History({
    generatePage: loadfailures.loadNextTestType,
});
g_history.parseCrossDashboardParameters();

window.addEventListener('load', function() {
    // FIXME: Come up with a better way to do this. This early return is just to avoid
    // executing this code when it's loaded in the unittests.
    if (!$('content'))
        return;
    loadfailures.loadNextTestType(g_history);
}, false);

})();
