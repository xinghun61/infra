// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"bytes"
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

// unmarshalJSONWithNumber unmarshals JSON, where numbers are unmarshaled as
// json.Number.
func unmarshalJSONWithNumber(data []byte, dest interface{}) error {
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	return decoder.Decode(dest)
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

// getReturnCode returns a return code value for a given error. It handles the
// returnCodeError type specially, returning its integer value verbatim.
//
// The error returned by getReturnCode is the same as the input error, unless
// the input error was a zero return code, in which case it will be nil.
func getReturnCode(err error) (int, error) {
	if err == nil {
		return 0, nil
	}
	if rc, ok := errors.Unwrap(err).(returnCodeError); ok {
		if rc == 0 {
			return 0, nil
		}
		return int(rc), err
	}
	return 1, err
}
