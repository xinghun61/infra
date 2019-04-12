// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"infra/libs/skylab/inventory"
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

func writeSkylabLabData(root string, lab *allLabs) error {
	return inventory.WriteLab(lab.Skylab, filepath.Join(root, "data", "skylab"))
}

func writeAutotestProdLabData(root string, lab *allLabs) error {
	return inventory.WriteLab(lab.AutotestProd, filepath.Join(root, "data", "prod"))
}
