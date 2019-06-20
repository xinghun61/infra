// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package queries

import (
	"go.chromium.org/luci/common/tsmon/metric"
)

var (
	retryUniqueUUID = metric.NewCounter(
		"chromeos/drone-queen/irregular-event/retry-unique-uuid",
		"retry when attempting to generate a unique drone UUID",
		nil)
)
