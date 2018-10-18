/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

var firstCharMap;

function setUp() {
  firstCharMap = new Object();
}

function testAddItemToFirstCharMap_OneWordLabel() {
  _AC_AddItemToFirstCharMap(firstCharMap, 'h', 'Hot');
  let hArray = firstCharMap['h'];
  assertEquals(1, hArray.length);
  assertEquals('Hot', hArray[0].value);

  _AC_AddItemToFirstCharMap(firstCharMap, '-', '-Hot');
  _AC_AddItemToFirstCharMap(firstCharMap, 'h', '-Hot');
  let minusArray = firstCharMap['-'];
  assertEquals(1, minusArray.length);
  assertEquals('-Hot', minusArray[0].value);
  hArray = firstCharMap['h'];
  assertEquals(2, hArray.length);
  assertEquals('Hot', hArray[0].value);
  assertEquals('-Hot', hArray[1].value);
}

function testAddItemToFirstCharMap_KeyValueLabels() {
  _AC_AddItemToFirstCharMap(firstCharMap, 'p', 'Priority-High');
  _AC_AddItemToFirstCharMap(firstCharMap, 'h', 'Priority-High');
  let pArray = firstCharMap['p'];
  assertEquals(1, pArray.length);
  assertEquals('Priority-High', pArray[0].value);
  let hArray = firstCharMap['h'];
  assertEquals(1, hArray.length);
  assertEquals('Priority-High', hArray[0].value);
}
