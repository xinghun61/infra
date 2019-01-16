// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd_test

import (
	"fmt"

	"infra/cmd/skylab/internal/cipd"
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

func ExampleClient() {
	got, _ := cipd.InstalledPackages(fakeClient{}, "/nonexistent")
	fmt.Printf("%#v", got)
	// Output:
	// []cipd.Package{cipd.Package{Package:"chromiumos/infra/skylab/linux-amd64", Pin:cipd.Pin{Package:"chromiumos/infra/skylab/linux-amd64", InstanceID:"Z5AzvrgQMH45eCuQymTro7yVwwJOny0Tf5vFRks4A-4C"}, Tracking:"latest"}}
}
