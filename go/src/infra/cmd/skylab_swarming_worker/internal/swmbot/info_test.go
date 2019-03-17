// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swmbot

import (
	"path/filepath"
	"strings"
	"testing"

	"github.com/kylelemons/godebug/pretty"

	"infra/cmd/skylab_swarming_worker/internal/lucifer"
)

func TestInfo_LuciferConfig(t *testing.T) {
	t.Parallel()
	b := &Info{
		AutotestPath:  "/usr/local/autotest",
		LuciferBinDir: "/opt/lucifer",
	}
	got := b.LuciferConfig()
	want := lucifer.Config{
		AutotestPath: "/usr/local/autotest",
		BinDir:       "/opt/lucifer",
	}
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("LuciferConfig() differs -want +got:\n %s", diff)
	}
}

func TestTask_StainlessURL(t *testing.T) {
	t.Parallel()
	task := &Task{
		RunID: "3e4391423c3a431a",
	}
	// Stainless browser expects directory paths to contain a trailing /
	suffix := filepath.Join("swarming-3e4391423c3a4310", "a") + "/"
	got := task.StainlessURL()
	if !strings.HasSuffix(got, suffix) {
		t.Errorf("Stainless URL does not have suffix %s: %s", suffix, got)
	}
}
