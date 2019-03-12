// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swmbot

import (
	"testing"

	"github.com/kylelemons/godebug/pretty"

	"infra/cmd/skylab_swarming_worker/internal/lucifer"
)

func TestBot_LuciferConfig(t *testing.T) {
	t.Parallel()
	b := &Bot{
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
