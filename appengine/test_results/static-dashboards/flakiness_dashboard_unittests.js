// Copyright (C) 2011 Google Inc. All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are
// met:
//
//     * Redistributions of source code must retain the above copyright
// notice, this list of conditions and the following disclaimer.
//     * Redistributions in binary form must reproduce the above
// copyright notice, this list of conditions and the following disclaimer
// in the documentation and/or other materials provided with the
// distribution.
//     * Neither the name of Google Inc. nor the names of its
// contributors may be used to endorse or promote products derived from
// this software without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
// "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
// LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
// A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
// OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
// SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
// LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
// DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
// THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

module('flakiness_dashboard');

// FIXME(jparent): Rename this once it isn't globals.
function resetGlobals()
{
    allExpectations = null;
    g_resultsByBuilder = {};
    g_allTestsTrie = null;
    var historyInstance = new history.History(flakinessConfig);
    // FIXME(jparent): Remove this once global isn't used.
    g_history = historyInstance;
    g_testToResultsMap = {};

    for (var key in history.DEFAULT_CROSS_DASHBOARD_STATE_VALUES)
        historyInstance.crossDashboardState[key] = history.DEFAULT_CROSS_DASHBOARD_STATE_VALUES[key];

    LOAD_BUILDBOT_DATA({
        "no_upload_test_types": [
            "webkit_unit_tests"
        ],
        'masters': [{
            name: 'ChromiumWebkit',
            url_name: "chromium.webkit",
            tests: {
                'layout-tests': {'builders': ['WebKit Linux', 'WebKit Linux (dbg)', 'WebKit Linux (deps)', 'WebKit Mac10.7', 'WebKit Win', 'WebKit Win (dbg)']},
                'unit_tests': {'builders': ['Linux Tests']},
            },
            groups: ['@ToT Chromium', '@ToT Blink'],
        },{
            name :'ChromiumWin',
            url_name: "chromium.win",
            tests: {
                'ash_unittests': {'builders': ['XP Tests (1)', 'Win7 Tests (1)']},
                'unit_tests': {'builders': ['Linux Tests']},
            },
            groups: ['@ToT Chromium'],
        }],
    });

   return historyInstance;
}

var FAILURE_MAP = {"A": "AUDIO", "C": "CRASH", "F": "TEXT", "I": "IMAGE", "O": "MISSING",
    "N": "NO DATA", "P": "PASS", "T": "TIMEOUT", "Y": "NOTRUN", "X": "SKIP", "Z": "IMAGE+TEXT"}

test('splitTestList', 1, function() {
    var historyInstance = new history.History(flakinessConfig);
    // FIXME(jparent): Remove this once global isn't used.
    g_history = historyInstance;
    historyInstance.dashboardSpecificState.tests = 'test.foo test.foo1\ntest.foo2\ntest.foo3,foo\\bar\\baz.html';
    equal(splitTestList().toString(), 'test.foo,test.foo1,test.foo2,test.foo3,foo/bar/baz.html');
});

test('headerForTestTableHtml', 1, function() {
    var container = document.createElement('div');
    container.innerHTML = headerForTestTableHtml();
    equal(container.querySelectorAll('input').length, 4);
});

test('htmlForIndividualTestOnAllBuilders', 1, function() {
    resetGlobals();
    g_history.dashboardSpecificState.showChrome = true;
    equal(htmlForIndividualTestOnAllBuilders('foo/nonexistant.html'), '<div class="not-found">Test not found. Either it does not exist, is skipped or passes on all recorded runs.</div>');
    g_history.dashboardSpecificState.showChrome = false;
});

test('htmlForIndividualTestOnAllBuildersWithResultsLinksNonexistant', 1, function() {
    resetGlobals();
    g_history.dashboardSpecificState.showChrome = true;
    equal(htmlForIndividualTestOnAllBuildersWithResultsLinks('foo/nonexistant.html'),
        '<div class="not-found">Test not found. Either it does not exist, is skipped or passes on all recorded runs.</div>' +
        '<div class=expectations test=foo/nonexistant.html>' +
            '<div>' +
                '<span class=link onclick="g_history.setQueryParameter(\'showExpectations\', true)">Show results</span> | ' +
                '<span class=link onclick="g_history.setQueryParameter(\'showLargeExpectations\', true)">Show large thumbnails</span> | ' +
                '<b>Only shows actual results/diffs from the most recent *failure* on each bot.</b>' +
            '</div>' +
        '</div>');
    g_history.dashboardSpecificState.showChrome = false;
});

test('htmlForIndividualTestOnAllBuildersWithResultsLinks', 1, function() {
    resetGlobals();
    g_history.dashboardSpecificState.showChrome = true;

    var builder = new builders.Builder('DummyMaster', 'WebKit Linux');
    g_resultsByBuilder[builder.key()] = {buildNumbers: [2, 1], chromeRevision: [1234, 1233], failure_map: FAILURE_MAP};

    var test = 'dummytest.html';
    var resultsObject = createResultsObjectForTest(test, builder);
    resultsObject.rawResults = [[1, 'F']];
    resultsObject.rawTimes = [[1, 0]];
    resultsObject.bugs = ["crbug.com/1234", "webkit.org/5678"];
    g_testToResultsMap[test] = [resultsObject];

    equal(htmlForIndividualTestOnAllBuildersWithResultsLinks(test),
        '<table class=test-table onclick="showPopup(event)"><thead><tr>' +
                '<th sortValue=test><div class=table-header-content><span></span><span class=header-text>test</span></div></th>' +
                '<th sortValue=bugs><div class=table-header-content><span></span><span class=header-text>bugs</span></div></th>' +
                '<th sortValue=expectations><div class=table-header-content><span></span><span class=header-text>expectations</span></div></th>' +
                '<th sortValue=slowest><div class=table-header-content><span></span><span class=header-text>slowest run</span></div></th>' +
                '<th sortValue=flakiness colspan=10000><div class=table-header-content><span></span><span class=header-text>flakiness (numbers are runtimes in seconds)</span></div></th>' +
            '</tr></thead>' +
            '<tbody>' +
                '<tr><td class="master-name" colspan=5>DummyMaster</td></tr>' +
                '<tr builder="DummyMaster:WebKit Linux" test="dummytest.html">' +
                '<td class="test-link builder-name">WebKit Linux' +
                '<td class=options-container>' +
                    '<div><a href="http://crbug.com/1234">crbug.com/1234</a></div>' +
                    '<div><a href="http://webkit.org/5678">webkit.org/5678</a></div>' +
                '<td class=options-container><td>' +
                '<td class="results-container">' +
                    '<div title="TEXT. Click for more info." class="results TEXT"></div>' +
                    '<div title="NO DATA. Click for more info." class="results NODATA">?</div>' +
                '</td>' +
            '</tbody>' +
        '</table>' +
        '<div>The following builders either don\'t run this test (e.g. it\'s skipped) or all recorded runs passed:</div>' +
        '<div class=skipped-builder-list>' +
            '<div class=skipped-builder>chromium.webkit:WebKit Linux</div><div class=skipped-builder>chromium.webkit:WebKit Linux (dbg)</div><div class=skipped-builder>chromium.webkit:WebKit Linux (deps)</div><div class=skipped-builder>chromium.webkit:WebKit Mac10.7</div><div class=skipped-builder>chromium.webkit:WebKit Win</div><div class=skipped-builder>chromium.webkit:WebKit Win (dbg)</div>' +
        '</div>' +
        '<div class=expectations test=dummytest.html>' +
            '<div><span class=link onclick="g_history.setQueryParameter(\'showExpectations\', true)">Show results</span> | ' +
            '<span class=link onclick="g_history.setQueryParameter(\'showLargeExpectations\', true)">Show large thumbnails</span> | ' +
            '<b>Only shows actual results/diffs from the most recent *failure* on each bot.</b></div>' +
        '</div>');
    g_history.dashboardSpecificState.showChrome = false;
});

test('individualTestsForSubstringList', 2, function() {
    resetGlobals();

    var builder = new builders.Builder('chromium.webkit', 'WebKit Linux');
    g_resultsByBuilder[builder.key()] = {
        buildNumbers: [2, 1],
        chromeRevision: [1234, 1233],
        failure_map: FAILURE_MAP,
        tests: {
            'foo/one.html': { results: [1, 'F'], times: [1, 0] },
            'virtual/foo/one.html': { results: [1, 'F'], times: [1, 0] },
        }
    };

    g_history.dashboardSpecificState.showChrome = true;
    var testToMatch = 'foo/one.html';
    g_history.dashboardSpecificState.tests = testToMatch;
    deepEqual(individualTestsForSubstringList(), [testToMatch, 'virtual/foo/one.html']);

    g_history.dashboardSpecificState.showChrome = false;
    deepEqual(individualTestsForSubstringList(), [testToMatch]);
});

test('htmlForIndividualTest', 2, function() {
    var historyInstance = resetGlobals();
    var test = 'foo/nonexistant.html';

    historyInstance.dashboardSpecificState.showChrome = false;

    equal(htmlForIndividualTest(test), htmlForIndividualTestOnAllBuilders(test) +
        '<a href="#useTestData=true" target="_blank">Pop out in a new tab</a>');

    historyInstance.dashboardSpecificState.showChrome = true;

    equal(htmlForIndividualTest(test),
        '<h2><a href="' + TEST_URL_BASE_PATH_FOR_BROWSING + 'foo/nonexistant.html" target="_blank">foo/nonexistant.html</a></h2>' +
        htmlForIndividualTestOnAllBuildersWithResultsLinks(test));
});

test('linkifyBugs', 4, function() {
    equal(linkifyBugs(["crbug.com/1234", "webkit.org/5678"]),
        '<div><a href="http://crbug.com/1234">crbug.com/1234</a></div><div><a href="http://webkit.org/5678">webkit.org/5678</a></div>');
    equal(linkifyBugs(["crbug.com/1234"]), '<div><a href="http://crbug.com/1234">crbug.com/1234</a></div>');
    equal(linkifyBugs(["Bug(nick)"]), '<div>Bug(nick)</div>');
    equal(linkifyBugs([]), '');
});

test('htmlForSingleTestRow', 1, function() {
    var historyInstance = resetGlobals();
    var builder = new builders.Builder('dummyMaster', 'dummyBuilder');
    var test = createResultsObjectForTest('foo/exists.html', builder);
    historyInstance.dashboardSpecificState.showNonFlaky = true;
    var chromeRevisions = [1234, 1233];
    g_resultsByBuilder[builder.key()] = {buildNumbers: [2, 1], chromeRevision: chromeRevisions, failure_map: FAILURE_MAP};
    test.rawResults = [[1, 'F'], [2, 'I']];
    test.rawTimes = [[1, 0], [2, 5]];
    var expected = '<tr builder="dummyMaster:dummyBuilder" test="foo/exists.html">' +
        '<td class="test-link"><span class="link" onclick="g_history.setQueryParameter(\'tests\',\'foo/exists.html\');">foo/exists.html</span>' +
        '<td class=options-container><a class="file-new-bug" href="https://code.google.com/p/chromium/issues/entry?template=Layout%20Test%20Failure&summary=Layout%20Test%20foo%2Fexists.html%20is%20failing&comment=The%20following%20layout%20test%20is%20failing%20on%20%5Binsert%20platform%5D%0A%0Afoo%2Fexists.html%0A%0AProbable%20cause%3A%0A%0A%5Binsert%20probable%20cause%5D">File new bug</a>' +
        '<td class=options-container>' +
        '<td>' +
        '<td class="results-container">' +
            '<div title="TEXT. Click for more info." class="results TEXT"></div>' +
            '<div title="IMAGE. Click for more info." class="results IMAGE">5</div>' +
        '</td>';

    equal(htmlForSingleTestRow(test, false, chromeRevisions), expected);
});

test('htmlForSingleTestRowWithFlakyResult', 1, function() {
    var historyInstance = resetGlobals();
    var builder = new builders.Builder('dummyMaster', 'dummyBuilder');
    var test = createResultsObjectForTest('foo/exists.html', builder);
    historyInstance.dashboardSpecificState.showNonFlaky = true;
    var chromeRevisions = [1234, 1233];
    g_resultsByBuilder[builder.key()] = {buildNumbers: [2, 1], chromeRevision: chromeRevisions, failure_map: FAILURE_MAP};
    test.rawResults = [[1, 'F'], [2, 'IP']];
    test.rawTimes = [[1, 0], [2, 5]];
    var expected = '<tr builder="dummyMaster:dummyBuilder" test="foo/exists.html">' +
        '<td class="test-link"><span class="link" onclick="g_history.setQueryParameter(\'tests\',\'foo/exists.html\');">foo/exists.html</span>' +
        '<td class=options-container><a class="file-new-bug" href="https://code.google.com/p/chromium/issues/entry?template=Layout%20Test%20Failure&summary=Layout%20Test%20foo%2Fexists.html%20is%20failing&comment=The%20following%20layout%20test%20is%20failing%20on%20%5Binsert%20platform%5D%0A%0Afoo%2Fexists.html%0A%0AProbable%20cause%3A%0A%0A%5Binsert%20probable%20cause%5D">File new bug</a>' +
        '<td class=options-container>' +
        '<td>' +
        '<td class="results-container">' +
            '<div title="TEXT. Click for more info." class="results TEXT"></div>' +
            '<div title="IMAGE PASS . Click for more info." class="results FLAKY">5</div>' +
        '</td>';

    equal(htmlForSingleTestRow(test, false, chromeRevisions), expected);
});

test('lookupVirtualTestSuite', 2, function() {
    equal(lookupVirtualTestSuite('fast/canvas/foo.html'), '');
    equal(lookupVirtualTestSuite('virtual/gpu/fast/canvas/foo.html'), 'virtual/gpu/fast/canvas');
});

test('baseTest', 2, function() {
    equal(baseTest('fast/canvas/foo.html', ''), 'fast/canvas/foo.html');
    equal(baseTest('virtual/gpu/fast/canvas/foo.html', 'virtual/gpu/fast/canvas'), 'fast/canvas/foo.html');
});

test('sortTests', 4, function() {
    var builder = new builders.Builder('dummyMaster', 'dummyBuilder');
    var test1 = createResultsObjectForTest('foo/test1.html', builder);
    var test2 = createResultsObjectForTest('foo/test2.html', builder);
    var test3 = createResultsObjectForTest('foo/test3.html', builder);
    test1.expectations = 'b';
    test2.expectations = 'a';
    test3.expectations = '';

    var tests = [test1, test2, test3];
    sortTests(tests, 'expectations', FORWARD);
    deepEqual(tests, [test2, test1, test3]);
    sortTests(tests, 'expectations', BACKWARD);
    deepEqual(tests, [test3, test1, test2]);

    test1.bugs = 'b';
    test2.bugs = 'a';
    test3.bugs = '';

    var tests = [test1, test2, test3];
    sortTests(tests, 'bugs', FORWARD);
    deepEqual(tests, [test2, test1, test3]);
    sortTests(tests, 'bugs', BACKWARD);
    deepEqual(tests, [test3, test1, test2]);
});

test('popup', 2, function() {
    ui.popup.show(document.body, 'dummy content');
    ok(document.querySelector('#popup'));
    ui.popup.hide();
    ok(!document.querySelector('#popup'));
});

test('gpuResultsPath', 3, function() {
  equal(gpuResultsPath('777777', 'Win7 Release (ATI)'), '777777_Win7_Release_ATI_');
  equal(gpuResultsPath('123', 'GPU Linux (dbg)(NVIDIA)'), '123_GPU_Linux_dbg_NVIDIA_');
  equal(gpuResultsPath('12345', 'GPU Mac'), '12345_GPU_Mac');
});

test('TestTrie', 3, function() {
    resetGlobals();
    var allBuilders = [
        new builders.Builder("DummmyMaster", "Dummy Chromium Windows Builder"),
        new builders.Builder("DummmyMaster", "Dummy GTK Linux Builder"),
        new builders.Builder("DummmyMaster", "Dummy Apple Mac Lion Builder")
    ];

    var resultsByBuilder = {
        "DummmyMaster:Dummy Chromium Windows Builder": {
            tests: {
                "foo": true,
                "foo/bar/1.html": true,
                "foo/bar/baz": true
            }
        },
        "DummmyMaster:Dummy GTK Linux Builder": {
            tests: {
                "bar": true,
                "foo/1.html": true,
                "foo/bar/2.html": true,
                "foo/bar/baz/1.html": true,
            }
        },
        "DummmyMaster:Dummy Apple Mac Lion Builder": {
            tests: {
                "foo/bar/3.html": true,
                "foo/bar/baz/foo": true,
            }
        }
    };
    var expectedTrie = {
        "foo": {
            "bar": {
                "1.html": true,
                "2.html": true,
                "3.html": true,
                "baz": {
                    "1.html": true,
                    "foo": true
                }
            },
            "1.html": true
        },
        "bar": true
    }

    var trie = new TestTrie(allBuilders, resultsByBuilder);
    deepEqual(trie._trie, expectedTrie);

    var leafsOfCompleteTrieTraversal = [];
    var expectedLeafs = ["foo/bar/1.html", "foo/bar/baz/1.html", "foo/bar/baz/foo", "foo/bar/2.html", "foo/bar/3.html", "foo/1.html", "bar"];
    trie.forEach(function(triePath) {
        leafsOfCompleteTrieTraversal.push(triePath);
    });
    deepEqual(leafsOfCompleteTrieTraversal, expectedLeafs);

    var leafsOfPartialTrieTraversal = [];
    expectedLeafs = ["foo/bar/1.html", "foo/bar/baz/1.html", "foo/bar/baz/foo", "foo/bar/2.html", "foo/bar/3.html"];
    trie.forEach(function(triePath) {
        leafsOfPartialTrieTraversal.push(triePath);
    }, "foo/bar");
    deepEqual(leafsOfPartialTrieTraversal, expectedLeafs);
});

test('shouldShowTest', 9, function() {
    var historyInstance = new history.History(flakinessConfig);
    historyInstance.parseParameters();
    // FIXME(jparent): Change to use the flakiness_dashboard's history object
    // once it exists, rather than tracking global.
    g_history = historyInstance;
    var builder = new builders.Builder('dummyMaster', 'dummyBuilder');
    var test = createResultsObjectForTest('foo/test.html', builder);

    equal(shouldShowTest(test), false, 'default layout test, hide it.');
    historyInstance.dashboardSpecificState.showNonFlaky = true;
    equal(shouldShowTest(test), true, 'show correct expectations.');
    historyInstance.dashboardSpecificState.showNonFlaky = false;

    test = createResultsObjectForTest('foo/test.html', builder);
    test.expectations = "WONTFIX";
    equal(shouldShowTest(test), false, 'by default hide wontfix');
    historyInstance.dashboardSpecificState.showWontFix = true;
    equal(shouldShowTest(test), true, 'show wontfix');
    historyInstance.dashboardSpecificState.showWontFix = false;

    test = createResultsObjectForTest('foo/test.html', builder);
    test.expectations = "SKIP";
    equal(shouldShowTest(test), false, 'we hide skip tests by default');
    historyInstance.dashboardSpecificState.showSkip = true;
    equal(shouldShowTest(test), true, 'show skip test');
    historyInstance.dashboardSpecificState.showSkip = false;

    test = createResultsObjectForTest('foo/test.html', builder);
    test.isFlaky = true;
    equal(shouldShowTest(test), false, 'hide flaky tests by default');
    historyInstance.dashboardSpecificState.showFlaky = true;
    equal(shouldShowTest(test), true, 'show flaky test');
    historyInstance.dashboardSpecificState.showFlaky = false;

    test = createResultsObjectForTest('foo/test.html', builder);
    historyInstance.crossDashboardState.testType = 'not layout tests';
    equal(shouldShowTest(test), true, 'show all non layout tests');
});

test('collapsedRevisionListChromium', 1, function() {
    resetGlobals();
    var test = 'dummytest.html';

    var builder1 = new builders.Builder('Master1', 'WebKit Linux 1');
    // Note: r1235 results were generated twice by two separate builds.
    g_resultsByBuilder[builder1.key()] = {builder: builder1, buildNumbers: [2, 1, 3, 4], chromeRevision: [1235, 1235, 1234, 1232], failure_map: FAILURE_MAP};

    var builder2 = new builders.Builder('Master1', 'WebKit Linux 2');
    g_resultsByBuilder[builder2.key()] = {builder: builder2, buildNumbers: [4, 5], chromeRevision: [1236, 1234], failure_map: FAILURE_MAP};

    var resultsObject1 = createResultsObjectForTest(test, builder1);
    var resultsObject2 = createResultsObjectForTest(test, builder2);

    var result = collapsedRevisionList([resultsObject1, resultsObject2]).join(',');
    var expected = [1236, 1235, 1235, 1234, 1232].join(',');
    equal(result, expected, 'collapsedRevisionList result should be the unique chromium builds, sorted in descending order');
});

test('collapsedRevisionListChromiumGitHashes', 1, function() {
    resetGlobals();
    var test = 'dummytest.html';

    var builder1 = new builders.Builder('Master1', 'WebKit Linux 1');
    // Note: r1235 results were generated twice by two separate builds.
    g_resultsByBuilder[builder1.key()] = {builder: builder1, buildNumbers: [2, 1, 3, 4], chromeRevision: ['1234', 'asdf', '1111', '2222'], failure_map: FAILURE_MAP};

    var builder2 = new builders.Builder('Master1', 'WebKit Linux 2');
    g_resultsByBuilder[builder2.key()] = {builder: builder2, buildNumbers: [4, 5], chromeRevision: ['asdf', '2345'], failure_map: FAILURE_MAP};

    var resultsObject1 = createResultsObjectForTest(test, builder1);
    var resultsObject2 = createResultsObjectForTest(test, builder2);

    var result = collapsedRevisionList([resultsObject1, resultsObject2]);
    equal(result, null, 'collapsedRevisionList result should be null if there are git hashes');
});


test('htmlForTestsWithMultipleRunsAtTheSameRevision', 6, function() {
    resetGlobals();
    g_history.dashboardSpecificState.showChrome = true;
    var test = 'dummytest.html';

    var builder1 = new builders.Builder('Master1', 'WebKit Linux (dbg)');
    // Note: r1235 results were generated thrice by three separate builds.
    g_resultsByBuilder[builder1.key()] = {buildNumbers: [4, 3, 2, 1, 0], chromeRevision: [1235, 1235, 1235, 1234, 1233], failure_map: FAILURE_MAP};

    var builder2 = new builders.Builder('Master1', 'WebKit Win (dbg)');
    g_resultsByBuilder[builder2.key()] = {buildNumbers: [6, 5], chromeRevision: [1236, 1234], failure_map: FAILURE_MAP};

    var resultsObject1 = createResultsObjectForTest(test, builder1);
    resultsObject1.rawResults = [[0, 'F'], [1, 'I'], [2, 'I'], [3, 'P'], [4, 'F']];
    resultsObject1.rawTimes = [[0, 0], [1, 0], [2, 0], [3, 0], [4, 0]];
    resultsObject1.bugs = ["crbug.com/1234", "crbug.com/5678", "crbug.com/9101112"];

    var resultsObject2 = createResultsObjectForTest(test, builder2);
    resultsObject2.rawResults = [[4, 'F'], [5, 'I']];
    resultsObject2.rawTimes = [[4, 0], [5, 5]];
    resultsObject2.bugs = ["crbug.com/one", "crbug.com/two"];

    g_testToResultsMap[test] = [resultsObject1, resultsObject2];
    var html = htmlForIndividualTestOnAllBuildersWithResultsLinks(test);
    equal(html,
        '<table class=test-table onclick="showPopup(event)"><thead><tr>' +
                '<th sortValue=test><div class=table-header-content><span></span><span class=header-text>test</span></div></th>' +
                '<th sortValue=bugs><div class=table-header-content><span></span><span class=header-text>bugs</span></div></th>' +
                '<th sortValue=expectations><div class=table-header-content><span></span><span class=header-text>expectations</span></div></th>' +
                '<th sortValue=slowest><div class=table-header-content><span></span><span class=header-text>slowest run</span></div></th>' +
                '<th sortValue=flakiness colspan=10000><div class=table-header-content><span></span><span class=header-text>flakiness (numbers are runtimes in seconds)</span></div></th>' +
            '</tr></thead>' +
            '<tbody>' +
                '<tr><td class="master-name" colspan=5>Master1</td></tr>' +
                '<tr builder="Master1:WebKit Linux (dbg)" test="dummytest.html">' +
                    '<td class="test-link builder-name">WebKit Linux (dbg)' +
                    '<td class=options-container>' +
                        '<div><a href="http://crbug.com/1234">crbug.com/1234</a></div>' +
                        '<div><a href="http://crbug.com/5678">crbug.com/5678</a></div>' +
                        '<div><a href="http://crbug.com/9101112">crbug.com/9101112</a></div>' +
                    '<td class=options-container><td><td class="results-container">' +
                        '<div title="Unknown result. Did not run tests." rev="1236" class="results interpolatedResult NODATA">?</div>' +
                        '<div title="TEXT. Click for more info." class="results TEXT"></div>' +
                        '<div title="IMAGE. Click for more info." class="results IMAGE"></div>' +
                        '<div title="IMAGE. Click for more info." class="results IMAGE"></div>' +
                        '<div title="PASS. Click for more info." class="results PASS"></div>' +
                        '<div title="PASS. Click for more info." class="results PASS"></div>' +
                    '</td>' +
                '<tr builder="Master1:WebKit Win (dbg)" test="dummytest.html">' +
                    '<td class="test-link builder-name">WebKit Win (dbg)' +
                    '<td class=options-container>' +
                        '<div><a href="http://crbug.com/one">crbug.com/one</a></div>' +
                        '<div><a href="http://crbug.com/two">crbug.com/two</a></div>' +
                    '<td class=options-container><td><td class="results-container">' +
                        '<div title="TEXT. Click for more info." class="results TEXT"></div>' +
                        '<div title="Unknown result. Did not run tests." rev="1235" class="results interpolatedResult TEXT">?</div>' +
                        '<div title="Unknown result. Did not run tests." rev="1235" class="results interpolatedResult TEXT">?</div>' +
                        '<div title="Unknown result. Did not run tests." rev="1235" class="results interpolatedResult TEXT">?</div>' +
                        '<div title="TEXT. Click for more info." class="results TEXT"></div>' +
                        '<div title="Unknown result. Did not run tests." rev="1233" class="results interpolatedResult NODATA">?</div>' +
                    '</td>' +
            '</tbody>' +
        '</table>' +
        '<div>The following builders either don\'t run this test (e.g. it\'s skipped) or all recorded runs passed:</div>' +
        '<div class=skipped-builder-list>' +
            '<div class=skipped-builder>chromium.webkit:WebKit Linux</div><div class=skipped-builder>chromium.webkit:WebKit Linux (dbg)</div><div class=skipped-builder>chromium.webkit:WebKit Linux (deps)</div><div class=skipped-builder>chromium.webkit:WebKit Mac10.7</div><div class=skipped-builder>chromium.webkit:WebKit Win</div><div class=skipped-builder>chromium.webkit:WebKit Win (dbg)</div>' +
        '</div>' +
        '<div class=expectations test=dummytest.html>' +
            '<div><span class=link onclick="g_history.setQueryParameter(\'showExpectations\', true)">Show results</span> | ' +
            '<span class=link onclick="g_history.setQueryParameter(\'showLargeExpectations\', true)">Show large thumbnails</span> | ' +
            '<b>Only shows actual results/diffs from the most recent *failure* on each bot.</b></div>' +
        '</div>');
    g_history.dashboardSpecificState.showChrome = false;

    var div = document.createElement("div");
    div.innerHTML = html;
    var table = div.children[0];
    equal(table.nodeName, "TABLE");
    var tbody = table.children[1];
    equal(tbody.nodeName, "TBODY");

    var showPopupForInterpolatedResultOriginal = showPopupForInterpolatedResult;
    var showPopupForBuildOriginal = showPopupForBuild;
    var showPopupCalls = [];
    showPopupForBuild = function(event, builder, buildIndex, test)
    {
        showPopupCalls.push("showPopupForBuild('" + builder + "', " + buildIndex + ", '" + test + "')");
    }

    showPopupForInterpolatedResult = function(event, revision)
    {
        showPopupCalls.push("showPopupForInterpolatedResult('" + revision + "')");
    }

    for (var rowIndex = 0; rowIndex < tbody.children.length; ++rowIndex) {
        var row = tbody.children[rowIndex];
        if (row.children.length === 1)  // skip builder name row.
            continue;
        var results = row.children[4];
        equal(results.className, "results-container");
        for (var resultIndex = 0; resultIndex < results.children.length; ++resultIndex) {
            var event = { target: results.children[resultIndex] };
            showPopup(event);
        }
    }
    equal(showPopupCalls.join(),
        "showPopupForInterpolatedResult('1236')," +
        "showPopupForBuild('Master1:WebKit Linux (dbg)', 0, 'dummytest.html')," +
        "showPopupForBuild('Master1:WebKit Linux (dbg)', 1, 'dummytest.html')," +
        "showPopupForBuild('Master1:WebKit Linux (dbg)', 2, 'dummytest.html')," +
        "showPopupForBuild('Master1:WebKit Linux (dbg)', 3, 'dummytest.html')," +
        "showPopupForBuild('Master1:WebKit Linux (dbg)', 4, 'dummytest.html')," +
        "showPopupForBuild('Master1:WebKit Win (dbg)', 0, 'dummytest.html')," +
        "showPopupForInterpolatedResult('1235')," +
        "showPopupForInterpolatedResult('1235')," +
        "showPopupForInterpolatedResult('1235')," +
        "showPopupForBuild('Master1:WebKit Win (dbg)', 1, 'dummytest.html')," +
        "showPopupForInterpolatedResult('1233')"
    );

    showPopupForBuild = showPopupForBuildOriginal;
    showPopupForInterpolatedResult = showPopupForInterpolatedResultOriginal;
});

test('htmlForTestsWithMultipleRunsWithGitHash', 1, function() {
    resetGlobals();
    g_history.dashboardSpecificState.showChrome = true;
    var test = 'dummytest.html';

    var builder = new builders.Builder('Master1', 'WebKit Linux (dbg)');
    g_resultsByBuilder[builder.key()] = {buildNumbers: [0], chromeRevision: ['b7228ffd469f5d3f4a10952fb8e9a34acb2f0d4b'], failure_map: FAILURE_MAP};

    var resultsObject = createResultsObjectForTest(test, builder);
    resultsObject.rawResults = [[0, 'P']];
    resultsObject.rawTimes = [[0, 0]];
    resultsObject.bugs = ["crbug.com/1234"];

    g_testToResultsMap[test] = [resultsObject];
    equal(htmlForIndividualTestOnAllBuildersWithResultsLinks(test),
        '<table class=test-table onclick="showPopup(event)">' +
            '<thead><tr>' +
                '<th sortValue=test><div class=table-header-content><span></span><span class=header-text>test</span></div></th>' +
                '<th sortValue=bugs><div class=table-header-content><span></span><span class=header-text>bugs</span></div></th>' +
                '<th sortValue=expectations><div class=table-header-content><span></span><span class=header-text>expectations</span></div></th>' +
                '<th sortValue=slowest><div class=table-header-content><span></span><span class=header-text>slowest run</span></div></th>' +
                '<th sortValue=flakiness colspan=10000><div class=table-header-content><span></span><span class=header-text>flakiness (numbers are runtimes in seconds)</span></div></th>' +
            '</tr></thead>' +
            '<tbody>' +
                '<tr><td class="master-name" colspan=5>Master1</td></tr>' +
                '<tr builder="Master1:WebKit Linux (dbg)" test="dummytest.html">' +
                    '<td class="test-link builder-name">WebKit Linux (dbg)<td class=options-container><div><a href="http://crbug.com/1234">crbug.com/1234</a></div>' +
                    '<td class=options-container><td><td class="results-container">' +
                        '<div title="PASS. Click for more info." class="results PASS"></div>' +
                    '</td>' +
            '</tbody>' +
        '</table>' +
        '<div>The following builders either don\'t run this test (e.g. it\'s skipped) or all recorded runs passed:</div>' +
        '<div class=skipped-builder-list>' +
            '<div class=skipped-builder>chromium.webkit:WebKit Linux</div>' +
            '<div class=skipped-builder>chromium.webkit:WebKit Linux (dbg)</div>' +
            '<div class=skipped-builder>chromium.webkit:WebKit Linux (deps)</div>' +
            '<div class=skipped-builder>chromium.webkit:WebKit Mac10.7</div>' +
            '<div class=skipped-builder>chromium.webkit:WebKit Win</div>' +
            '<div class=skipped-builder>chromium.webkit:WebKit Win (dbg)</div>' +
        '</div>' +
        '<div class=expectations test=dummytest.html>' +
            '<div>' +
                '<span class=link onclick="g_history.setQueryParameter(\'showExpectations\', true)">Show results</span> | ' +
                '<span class=link onclick="g_history.setQueryParameter(\'showLargeExpectations\', true)">Show large thumbnails</span> | ' +
                '<b>Only shows actual results/diffs from the most recent *failure* on each bot.</b>' +
            '</div>' +
        '</div>');
    g_history.dashboardSpecificState.showChrome = false;
});

test('htmlForPopupForBuild', 2, function() {
    resetGlobals();

    var builder = new builders.Builder('Master1', 'WebKit Linux (dbg)');
    g_resultsByBuilder[builder.key()] = {
        buildNumbers: [4, 3],
        chromeRevision: [1235, 1233],
        chromeRevision: [1235, 1233],
        secondsSinceEpoch: [1234, 1234],
        failure_map: FAILURE_MAP
    };

    var tests = {}
    var basePath = 'http://build.chromium.org/p/';
    var name = 'Master1';
    builders.masters[name] = new builders.Master({name: name, url_name: name, tests: tests});

    equal(htmlForPopupForBuild(builder.key(), 0), '12/31/1969 4:20:34 PM' +
        '<ul>' +
            '<li>' +
                '<a href="http://build.chromium.org/p/Master1/builders/WebKit Linux (dbg)/builds/4" target="_blank">' +
                    'Build log' +
                '</a>' +
            '</li>' +
            '<li>Chromium: <a href="../../revision_range?start=1234&end=1235">r1234 to r1235</a></li>' +
            '<li>' +
                '<a href="https://storage.googleapis.com/chromium-layout-test-archives/WebKit_Linux__dbg_/4/layout-test-results.zip">' +
                    'layout-test-results.zip' +
                '</a>' +
            '</li>' +
        '</ul>');

    // This lacks a previous revision, so it can't show the right regression ranges.
    equal(htmlForPopupForBuild(builder.key(), 1), '12/31/1969 4:20:34 PM' +
        '<ul>' +
            '<li>' +
                '<a href="http://build.chromium.org/p/Master1/builders/WebKit Linux (dbg)/builds/3" target="_blank">' +
                    'Build log' +
                '</a>' +
            '</li>' +
            '<li>' +
                '<a href="https://storage.googleapis.com/chromium-layout-test-archives/WebKit_Linux__dbg_/3/layout-test-results.zip">' +
                    'layout-test-results.zip' +
                '</a>' +
            '</li>' +
        '</ul>');
});

test('htmlForPopupForBuildWithGitHashes', 1, function() {
    resetGlobals();

    var builder = new builders.Builder('Master1', 'WebKit Linux (dbg)');
    g_resultsByBuilder[builder.key()] = {
        buildNumbers: [4, 3],
        chromeRevision: ['asdf', 'qwer'],
        secondsSinceEpoch: [1234, 1234],
        failure_map: FAILURE_MAP
    };

    var tests = {}
    var basePath = 'http://build.chromium.org/p/';
    var name = 'Master1';
    builders.masters[name] = new builders.Master({name: name, url_name: name, tests: tests});

    equal(htmlForPopupForBuild(builder.key(), 0), '12/31/1969 4:20:34 PM' +
        '<ul>' +
            '<li>' +
                '<a href="http://build.chromium.org/p/Master1/builders/WebKit Linux (dbg)/builds/4" target="_blank">' +
                    'Build log' +
                '</a>' +
            '</li>' +
            '<li>' +
                '<a href="https://storage.googleapis.com/chromium-layout-test-archives/WebKit_Linux__dbg_/4/layout-test-results.zip">' +
                    'layout-test-results.zip' +
                '</a>' +
            '</li>' +
        '</ul>');
});
