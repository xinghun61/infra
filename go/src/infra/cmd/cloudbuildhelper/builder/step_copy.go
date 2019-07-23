// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package builder

import (
	"context"

	"go.chromium.org/luci/common/logging"
)

// runCopyBuildStep executes manifest.CopyBuildStep.
func runCopyBuildStep(ctx context.Context, inv *stepRunnerInv) error {
	src := inv.BuildStep.CopyBuildStep.Copy
	dst := inv.BuildStep.Dest
	logging.Infof(ctx, "Copying %q => %q", src, dst)
	return inv.Output.AddFromDisk(src, dst)
}
