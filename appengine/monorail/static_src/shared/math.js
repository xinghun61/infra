// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Get parameter of generated line using linear regression formula,
// using last n data points of values.
export function linearRegression(values, n) {
  let sumValues = 0;
  let indices = 0;
  let sqIndices = 0;
  let multiply = 0;
  let temp;
  for (let i = 0; i < n; i++) {
    temp = values[values.length-n+i];
    sumValues += temp;
    indices += i;
    sqIndices += i * i;
    multiply += i * temp;
  }
  // Calculate linear regression formula for values.
  const slope = (n * multiply - sumValues * indices) /
    (n * sqIndices - indices * indices);
  const intercept = (sumValues * sqIndices - indices * multiply) /
    (n * sqIndices - indices * indices);
  return [slope, intercept];
}
