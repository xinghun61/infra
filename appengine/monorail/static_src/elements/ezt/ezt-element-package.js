// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// This file bundles together all web components elements used on the
// legacy EZT pages. This is to avoid having issues with registering
// duplicate versions of dependencies.

import page from 'page';

import 'elements/framework/mr-dropdown/mr-account-dropdown.js';
import 'elements/ezt/mr-bulk-approval-update/mr-bulk-approval-update.js';
import 'elements/framework/links/mr-user-link/mr-user-link.js';
import 'elements/chops/chops-timestamp/chops-timestamp.js';

import 'elements/framework/mr-header/mr-header.js';
import 'elements/issue-list/mr-chart/mr-chart.js';
import 'elements/issue-detail/mr-flipper/mr-flipper.js';
import 'elements/framework/mr-code-font-toggle/mr-code-font-toggle.js';
import 'elements/ezt/ezt-comments.js';

// Register an empty set of page.js routes to allow the page() navigation
// function to work.
// Note: The EZT pages should NOT register the routes used by the SPA pages
// without significant refactoring because doing so will lead to unexpected
// routing behavior where the SPA is loaded on top of a server-rendered page
// rather than instead of.
page();
