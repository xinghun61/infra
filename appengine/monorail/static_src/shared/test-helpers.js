// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import axe from 'axe-core';

// TODO(seanmccullough): Move this into crdx/chopsui-npm if we decide this
// is worth using in other projects.

export async function auditA11y(element) {
  // Performance tip: try restricting the analysis using
  // https://github.com/dequelabs/axe-core/blob/develop/doc/API.md#use-resulttypes
  const options = {};

  // Adjust this set to make tests more/less permissible.
  const reportImpact = new Set(['critical', 'serious', 'moderate', 'minor']);
  const results = await axe.run(element, options);

  if (results.violations.length == 0) {
    return;
  }

  const msgs = ['Accessibility violations:'];
  results.violations.forEach((result) => {
    if (reportImpact.has(result.impact)) {
      msgs.push(`\n[${result.impact}] ${result.help}`);
      for (const node of result.nodes) {
        if (node.failureSummary) {
          msgs.push(node.failureSummary);
        }
        msgs.push(node.html);
      }
      msgs.push('---');
    }
  });

  throw new Error(msgs.join('\n'));
}
