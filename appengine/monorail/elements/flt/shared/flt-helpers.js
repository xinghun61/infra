/* Copyright 2019 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file.
 */

export const fltHelpers = Object.freeze({
  // With lists a and b, get the elements that are in a but not in b.
  // result = a - b
  arrayDifference: (listA, listB, equals) => {
    if (!equals) {
      equals = (a, b) => (a === b);
    }
    listA = listA || [];
    listB = listB || [];
    return listA.filter((a) => {
      return !listB.find((b) => (equals(a, b)));
    });
  },
});
