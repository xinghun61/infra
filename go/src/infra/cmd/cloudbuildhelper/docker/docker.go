// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package docker is a primitive wrapper over shelling out to 'docker' tool.
//
// Assumes 'docker' binary is in PATH.
package docker

import (
	"context"
	"io"
	"io/ioutil"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
)

// Build calls "docker build --iidfile out [args] - < [read from r]".
func Build(ctx context.Context, context io.Reader, args []string) (string, error) {
	tmpDir, err := ioutil.TempDir("", "cloudbuildhelper")
	if err != nil {
		return "", errors.Annotate(err, "failed to create temp directory").Err()
	}
	defer os.RemoveAll(tmpDir)

	cmdLine := []string{"docker", "build", "--iidfile", "imageid"}
	cmdLine = append(cmdLine, args...)
	cmdLine = append(cmdLine, "-")

	logging.Infof(ctx, "Running %q", strings.Join(cmdLine, " "))

	cmd := exec.CommandContext(ctx, cmdLine[0], cmdLine[1:]...)
	cmd.Dir = tmpDir
	cmd.Stdin = context
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return "", errors.Annotate(err, "docker build invocation failed").Err()
	}

	out, err := ioutil.ReadFile(filepath.Join(tmpDir, "imageid"))
	if err != nil {
		return "", errors.Annotate(err, "failed read --iidfile produced by docker build").Err()
	}
	return strings.TrimSpace(string(out)), nil
}
