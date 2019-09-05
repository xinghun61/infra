// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package builder

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/system/environ"
)

// runGoBuildStep executes manifest.GoBuildStep.
func runGoBuildStep(ctx context.Context, inv *stepRunnerInv) error {
	// Name of a file in inv.TempDir to drop the binary into.
	tmpName := "go_bin" + inv.TempSuffix

	// TODO(vadimsh): We can make this configurable via the YAML if necessary.
	extraEnv := environ.New(nil)
	extraEnv.Set("CGO_ENABLED", "0")
	extraEnv.Set("GOOS", "linux")
	extraEnv.Set("GOARCH", "amd64")

	env := environ.System()
	env.Update(extraEnv)

	// See https://github.com/golang/go/issues/33772 for the explanation about
	// buildid.
	args := []string{"go", "build", "-trimpath", "-ldflags=-buildid="}
	if logging.IsLogging(ctx, logging.Debug) {
		args = append(args, "-v")
	}
	args = append(args, "-o", tmpName, inv.BuildStep.GoBuildStep.GoBinary)

	logging.Infof(ctx, "Running %q",
		strings.Join(extraEnv.Sorted(), " ")+" "+strings.Join(args, " "))

	cmd := exec.CommandContext(ctx, args[0], args[1:]...)
	cmd.Dir = inv.TempDir
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Env = env.Sorted()
	if err := cmd.Run(); err != nil {
		return errors.Annotate(err, "go build invocation failed").Err()
	}

	logging.Infof(ctx, "Copying %q => %q", tmpName, inv.BuildStep.Dest)
	return inv.Output.AddFromDisk(
		filepath.Join(inv.TempDir, tmpName),
		inv.BuildStep.Dest)
}
