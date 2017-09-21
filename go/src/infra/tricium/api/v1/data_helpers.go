// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tricium

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"path"
	"path/filepath"
)

const (
	// ResultsPath stores the path to the RESULTS data type file.
	ResultsPath = "tricium/data/results.json"

	// ClangDetailsPath stores the path to the CLANG_DETAILS data type file.
	ClangDetailsPath = "tricium/data/clang_details.json"

	// FilesPath stores the path to the FILES data type file.
	FilesPath = "tricium/data/files.json"

	// GitFileDetailsPath stores the path to the GIT_FILE_DETAILS data type file.
	GitFileDetailsPath = "tricium/data/git_file_details.json"
)

// GetPathForDataType returns the file path to use for the provided Tricium data type.
func GetPathForDataType(t interface{}) (string, error) {
	switch t := t.(type) {
	case *Data_GitFileDetails:
		return GitFileDetailsPath, nil
	case *Data_Files:
		return FilesPath, nil
	case *Data_ClangDetails:
		return ClangDetailsPath, nil
	case *Data_Results:
		return ResultsPath, nil
	default:
		return "", fmt.Errorf("unknown path for data type, type: %T", t)
	}
}

// WriteDataType writes a Tricium data type to the file path assigned to the type.
func WriteDataType(prefix string, t interface{}) (string, error) {
	json, err := json.Marshal(t)
	if err != nil {
		return "", fmt.Errorf("failed to marshal: %v", err)
	}
	p, err := GetPathForDataType(t)
	if err != nil {
		return p, fmt.Errorf("failed to get path for type: %v", err)
	}
	path := path.Join(prefix, p)
	if err := os.MkdirAll(filepath.Dir(path), os.ModePerm); err != nil {
		return path, fmt.Errorf("failed to make directories for path: %v", err)
	}
	f, err := os.Create(path)
	if err != nil {
		return path, fmt.Errorf("failed to create file: %v", err)
	}
	defer f.Close()
	if _, err := f.Write(json); err != nil {
		return path, fmt.Errorf("failed to write to file: %v", err)
	}
	return path, nil
}

// ReadDataType reads a Tricium data type to the provided type.
func ReadDataType(prefix string, t interface{}) error {
	p, err := GetPathForDataType(t)
	if err != nil {
		return fmt.Errorf("failed to get path for type: %v", err)
	}
	path := path.Join(prefix, p)
	msg, err := ioutil.ReadFile(path)
	if err != nil {
		return fmt.Errorf("failed to read file: %v", err)
	}
	if err := json.Unmarshal(msg, &t); err != nil {
		return fmt.Errorf("failed to unmarshal: %v", err)
	}
	return nil
}
