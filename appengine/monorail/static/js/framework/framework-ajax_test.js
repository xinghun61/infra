/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * @fileoverview Tests for framework-ajax.js.
 */

var CS_env;

function setUp() {
  CS_env = {'token': 'd34db33f'};
}

function testPostData() {
  assertEquals(
    'token=d34db33f',
    CS_postData({}));
  assertEquals(
    'token=d34db33f',
    CS_postData({}, true));
  assertEquals(
    '',
    CS_postData({}, false));
  assertEquals(
    'a=5&b=foo&token=d34db33f',
    CS_postData({a: 5, b: 'foo'}));

  let unescaped = {};
  unescaped['f oo?'] = 'b&ar';
  assertEquals(
    'f%20oo%3F=b%26ar',
    CS_postData(unescaped, false));
}
