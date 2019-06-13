// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package artifacts

import (
	"io"
	"os"
	"path/filepath"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/gcloud/gs"
)

// DownloadFromGoogleStorage downloads autotest artifacts required to compute
// test metadata from the Google Storage folder remoteDir to local outDir.
//
// This function returns the local paths to the downloaded artifacts.
func DownloadFromGoogleStorage(client gs.Client, remoteDir gs.Path, outDir string) (LocalPaths, error) {
	lp := LocalPaths{
		ControlFilesArchive: filepath.Join(outDir, "control_files.tar"),
		TestSuitesArchive:   filepath.Join(outDir, "test_suites.tar.bz2"),
	}
	if err := downloadOne(client, remoteDir.Concat("control_files.tar"), lp.ControlFilesArchive); err != nil {
		return lp, errors.Annotate(err, "download from gs").Err()
	}
	if err := downloadOne(client, remoteDir.Concat("test_suites.tar.bz2"), lp.TestSuitesArchive); err != nil {
		return lp, errors.Annotate(err, "download from gs").Err()
	}
	return lp, nil
}

func downloadOne(client gs.Client, gsPath gs.Path, localPath string) error {
	r, err := client.NewReader(gsPath, 0, -1)
	if err != nil {
		return errors.Annotate(err, "download one").Err()
	}
	w, err := os.Create(localPath)
	if err != nil {
		return errors.Annotate(err, "download one").Err()
	}
	if _, err := io.Copy(w, r); err != nil {
		return errors.Annotate(err, "download %s to %s", gsPath, localPath).Err()
	}
	return nil
}
