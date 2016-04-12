/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */


function testKeepJustSummaryPrefixes_NoPrefixes() {
  assertEquals(
      '',
      TKR_keepJustSummaryPrefixes(''));

  assertEquals(
      '',
      TKR_keepJustSummaryPrefixes('Enter one line summary'));

  assertEquals(
      '',
      TKR_keepJustSummaryPrefixes('Translation problem [en]'));

  assertEquals(
      '',
      TKR_keepJustSummaryPrefixes('Crash at HH:MM'));
}

function testKeepJustSummaryPrefixes_WithColons() {
  assertEquals(
      'Security: ',
      TKR_keepJustSummaryPrefixes('Security:'));

  assertEquals(
      'Exploit: ',
      TKR_keepJustSummaryPrefixes('Exploit: remote exploit'));

  assertEquals(
      'XSS:Security: ',
      TKR_keepJustSummaryPrefixes('XSS:Security: rest of summary'));

  assertEquals(
      'XSS: Security: ',
      TKR_keepJustSummaryPrefixes('XSS: Security: rest of summary'));

  assertEquals(
      'XSS-Security: ',
      TKR_keepJustSummaryPrefixes('XSS-Security: rest of summary'));

  assertEquals(
      'XSS: Security: ',
      TKR_keepJustSummaryPrefixes('XSS: Security: rest [of] su:mmary'));

  assertEquals(
      'XSS-Security: ',
      TKR_keepJustSummaryPrefixes('XSS-Security: rest [of] su:mmary'));
}

function testKeepJustSummaryPrefixes_WithBrackets() {
  assertEquals(
      '[Printing] ',
      TKR_keepJustSummaryPrefixes('[Printing] problem with page'));

  assertEquals(
      '[Printing] ',
      TKR_keepJustSummaryPrefixes('[Printing]   problem with page'));

  assertEquals(
      '[l10n][en] ',
      TKR_keepJustSummaryPrefixes('[l10n][en]Translation problem'));
}
