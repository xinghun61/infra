// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"encoding/json"
	"io/ioutil"

	"infra/libs/skylab/inventory"
	"infra/libs/skylab/inventory/cmd/skmigration/internal/cmd/snapshotdevice"
	"path/filepath"

	"go.chromium.org/luci/common/errors"
)

type allLabs struct {
	AutotestProd *inventory.Lab
	AutotestDev  *inventory.Lab
	Skylab       *inventory.Lab
}

func loadAllLabsData(root string) (*allLabs, error) {
	var labs allLabs
	var err error
	if labs.AutotestProd, err = inventory.LoadLab(filepath.Join(root, "prod")); err != nil {
		return nil, errors.Annotate(err, "load autotest prod lab").Err()
	}
	if labs.AutotestDev, err = inventory.LoadLab(filepath.Join(root, "staging")); err != nil {
		return nil, errors.Annotate(err, "load autotest dev lab").Err()
	}
	if labs.Skylab, err = inventory.LoadLab(filepath.Join(root, "data", "skylab")); err != nil {
		return nil, errors.Annotate(err, "load skylab lab").Err()
	}
	return &labs, nil
}

func loadSnapshotData(dir string) ([]snapshotdevice.SnapshotDevice, error) {
	var devices []snapshotdevice.SnapshotDevice
	toRead, err := ioutil.ReadFile(filepath.Join(dir, "combine_lab_data.json"))
	if err != nil {
		return nil, err
	}
	if err := json.Unmarshal(toRead, &devices); err != nil {
		return nil, err
	}
	return devices, nil
}

func writeSkylabLabData(root string, lab *allLabs) error {
	return inventory.WriteLab(lab.Skylab, filepath.Join(root, "data", "skylab"))
}

func writeAutotestProdLabData(root string, lab *allLabs) error {
	return inventory.WriteLab(lab.AutotestProd, filepath.Join(root, "data", "prod"))
}
