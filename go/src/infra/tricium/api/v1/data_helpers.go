// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tricium

import (
	"fmt"
)

// GetPathForDataType returns the file path to use for the provided Tricium data type.
func GetPathForDataType(t interface{}) (string, error) {
	switch t := t.(type) {
	case *Data_GitFileDetails:
		return "tricium/data/git_file_details.json", nil
	case *Data_Files:
		return "tricium/data/files.json", nil
	case *Data_ClangDetails:
		return "tricium/data/clang_details.json", nil
	case *Data_Results:
		return "tricium/data/results.json", nil
	default:
		return "", fmt.Errorf("unknown path for data type, type: %T", t)
	}
}
