// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"testing"

	"github.com/kylelemons/godebug/pretty"
)

type fakeClient struct{}

func (fakeClient) InstalledPackages(root string) ([]byte, error) {
	return []byte(`{
  "result": {
    "": [
      {
        "package": "chromiumos/infra/skylab/linux-amd64",
        "pin": {
          "package": "chromiumos/infra/skylab/linux-amd64",
          "instance_id": "Z5AzvrgQMH45eCuQymTro7yVwwJOny0Tf5vFRks4A-4C"
        },
        "tracking": "latest"
      }
    ]
  }
}`), nil
}

func TestInstalledPackages(t *testing.T) {
	t.Parallel()
	got, err := InstalledPackages(fakeClient{}, "/nonexistent")
	if err != nil {
		t.Fatalf("InstalledPackages returned error: %s", err)
	}
	want := []Package{
		{
			Package: "chromiumos/infra/skylab/linux-amd64",
			Pin: Pin{
				Package:    "chromiumos/infra/skylab/linux-amd64",
				InstanceID: "Z5AzvrgQMH45eCuQymTro7yVwwJOny0Tf5vFRks4A-4C",
			},
			Tracking: "latest",
		},
	}
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("InstalledPackages returned bad result -want +got, %s", diff)
	}
}
