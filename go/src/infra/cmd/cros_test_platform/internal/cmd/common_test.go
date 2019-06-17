// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"infra/cmd/cros_test_platform/internal/testutils"
	"path/filepath"
	"testing"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"

	"go.chromium.org/luci/common/errors"
)

func TestExitCodeWithVanillaError(t *testing.T) {
	if exitCode(errors.New("vanilla")) != 1 {
		t.Errorf("wrong return code %d with untagged error, want 1", 1)
	}
}

func TestExitCodeWithWriteResponseErrors(t *testing.T) {
	ws, cleanup := testutils.CreateTempDirOrDie(t)
	defer cleanup()

	validPath := filepath.Join(ws, "output.json")
	invalidPath := filepath.Join(ws, "noSuchDir", "output.json")

	var cases = []struct {
		tag        string
		errorSoFar error
		outFile    string
		want       int
	}{
		{"nil error with successful write", nil, validPath, 0},
		{"nil error with failed write", nil, invalidPath, 1},
		{"non-nil error with successful write", errors.New("original error"), validPath, 2},
		{"non-nil error with failed write", errors.New("original error"), invalidPath, 1},
	}

	response := steps.EnumerationResponse{}
	for _, c := range cases {
		t.Run(c.tag, func(t *testing.T) {
			err := writeResponse(c.outFile, &response, c.errorSoFar)
			got := exitCode(err)
			if got != c.want {
				t.Errorf("incorrect exit code %d, want %d. Error was %s", got, c.want, err)
			}
		})
	}
}
