// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {SHARED_STYLES} from './shared-styles';

const $_documentContainer = document.createElement('template');

$_documentContainer.innerHTML = `<dom-module id="mr-shared-styles">
  <template>
    <style>
      ${SHARED_STYLES}
    </style>
  </template>
</dom-module>`;

document.head.appendChild($_documentContainer.content);
