/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

var feedData = {
    'open': [{name: 'New', doc: 'Newly reported'},
             {name: 'Started', doc: 'Work has begun'}],
    'closed': [{name: 'Fixed', doc: 'Problem was fixed'},
               {name: 'Invalid', doc: 'Bad issue report'}],
    'labels': [{name: 'Type-Defect', doc: 'Something is broken'},
               {name: 'Type-Enhancement', doc: 'It could be better'},
               {name: 'Priority-High', doc: 'Urgent'},
               {name: 'Priority-Low', doc: 'Not so urgent'},
               {name: 'Hot', doc: ''},
               {name: 'Cold', doc: ''}],
    'members': [{name: 'jrobbins', doc: ''},
                {name: 'jrobbins@chromium.org', doc: ''}],
    'excl_prefixes': [],
    'strict': false
};

function setUp() {
  TKR_autoCompleteFeedName = 'issueOptions';
}

/**
 * The assertEquals method cannot do element-by-element comparisons.
 * A search of how other teams write JS unit tests turned up this
 * way to compare arrays.
 */
function assertElementsEqual(arrayA, arrayB) {
  assertEquals(arrayA.join(' ;; '), arrayB.join(' ;; '));
}

function completionsEqual(strings, completions) {
  if (strings.length != completions.length) {
    return false;
  }
  for (var i = 0; i < strings.length; i++) {
    if (strings[i] != completions[i].value) {
      return false;
    }
  }
  return true;
}

function assertHasCompletion(s, acStore) {
  var ch = s.charAt(0).toLowerCase();
  var firstCharMapArray = acStore.firstCharMap_[ch];
  assertNotNull(!firstCharMapArray);
  for (var i = 0; i < firstCharMapArray.length; i++) {
    if (s == firstCharMapArray[i].value) return;
  }
  fail('completion ' + s + ' not found in acStore[' +
       acStoreToString(acStore) + ']');
}

function assertHasAllCompletions(stringArray, acStore) {
  for (var i = 0; i < stringArray.length; i++) {
    assertHasCompletion(stringArray[i], acStore);
  }
}

function acStoreToString(acStore) {
  var allCompletions = [];
  for (var ch in acStore.firstCharMap_) {
    if (acStore.firstCharMap_.hasOwnProperty(ch)) {
      var firstCharArray = acStore.firstCharMap_[ch];
      for (var i = 0; i < firstCharArray.length; i++) {
        allCompletions[firstCharArray[i].value] = true;
      }
    }
  }
  var parts = [];
  for (var comp in allCompletions) {
    if (allCompletions.hasOwnProperty(comp)) {
      parts.push(comp);
    }
  }
  return parts.join(', ');
}

function testSetUpStatusStore() {
  TKR_setUpStatusStore(feedData.open, feedData.closed);
  assertElementsEqual(
      ['New', 'Started', 'Fixed', 'Invalid'],
      TKR_statusWords);
  assertHasAllCompletions(
      ['New', 'Started', 'Fixed', 'Invalid'],
      TKR_statusStore);
}

function testSetUpSearchStore() {
  TKR_setUpSearchStore(
      feedData.labels, feedData.members, feedData.open, feedData.closed);
  assertHasAllCompletions(
      ['status:New', 'status:Started', 'status:Fixed', 'status:Invalid',
       '-status:New', '-status:Started', '-status:Fixed', '-status:Invalid',
       'Type=Defect', '-Type=Defect', 'Type=Enhancement', '-Type=Enhancement',
       'label:Hot', 'label:Cold', '-label:Hot', '-label:Cold',
       'owner:jrobbins', 'cc:jrobbins', '-owner:jrobbins', '-cc:jrobbins',
       'summary:', 'opened-after:today-1', 'commentby:me', 'reporter:me'],
      TKR_searchStore);
}

function testSetUpQuickEditStore() {
  TKR_setUpQuickEditStore(
      feedData.labels, feedData.members, feedData.open, feedData.closed);
  assertHasAllCompletions(
      ['status=New', 'status=Started', 'status=Fixed', 'status=Invalid',
       'Type=Defect', 'Type=Enhancement', 'Hot', 'Cold', '-Hot', '-Cold',
       'owner=jrobbins', 'owner=me', 'cc=jrobbins', 'cc=me', 'cc=-jrobbins',
       'cc=-me', 'summary=""', 'owner=----'],
      TKR_quickEditStore);
}

function testSetUpLabelStore() {
  TKR_setUpLabelStore(feedData.labels);
  assertHasAllCompletions(
      ['Type-Defect', 'Type-Enhancement', 'Hot', 'Cold'],
      TKR_labelStore);
}

function testSetUpMembersStore() {
  TKR_setUpMemberStore(feedData.members);
  assertHasAllCompletions(
      ['jrobbins', 'jrobbins@chromium.org'],
      TKR_memberListStore);
}
