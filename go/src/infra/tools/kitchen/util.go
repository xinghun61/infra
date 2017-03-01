// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"io"
	"os"

	"github.com/luci/luci-go/common/errors"
)

func encodeJSONToPath(path string, obj interface{}) (err error) {
	fd, err := os.Create(path)
	if err != nil {
		return errors.Annotate(err).Reason("failed to create output file").Err()
	}
	defer func() {
		closeErr := fd.Close()
		if closeErr != nil && err == nil {
			err = errors.Annotate(closeErr).Reason("failed to close output file").Err()
		}
	}()
	if err = json.NewEncoder(fd).Encode(obj); err != nil {
		return errors.Annotate(err).Reason("failed to write encoded object").Err()
	}
	return nil
}

// ensureDir ensures dir at path exists.
// Returned errors are annotated.
func ensureDir(path string) error {
	if err := os.MkdirAll(path, 0755); err != nil && !os.IsExist(err) {
		return errors.Annotate(err).Reason("could not create temp dir %(dir)q").
			D("dir", path).
			Err()
	}
	return nil
}

// dirHashFiles returns true if the directory contains files/subdirectories.
// If it does not exist, return an os.IsNonExist error.
func dirHasFiles(path string) (bool, error) {
	dir, err := os.Open(path)
	if err != nil {
		return false, err
	}
	defer dir.Close()

	names, err := dir.Readdirnames(1)
	if err != nil && err != io.EOF {
		return false, errors.Annotate(err).Reason("could not read dir %(dir)q").
			D("dir", path).
			Err()
	}

	return len(names) > 0, nil
}
