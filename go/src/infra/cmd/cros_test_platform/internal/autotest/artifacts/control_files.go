// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package artifacts

import (
	"archive/tar"
	"compress/bzip2"
	"io"
	"os"
	"path/filepath"

	"go.chromium.org/luci/common/errors"
)

// LocalPaths points to locally downloaded copies of Autotest build artifacts.
type LocalPaths struct {
	// Path to test_suites.tar.bz2
	// This archive contains the test suite control files and is ~4 MiB.
	TestSuitesArchive string
	// Path to downloaded control_files.tar
	// This archive contains the test control files and is ~10 MiB
	ControlFilesArchive string
}

// ExtractControlFiles extracts Autotest control files from build artifacts
// downloaded locally.
//
// On success, outdir contains the unarchived control files.
func ExtractControlFiles(paths LocalPaths, outdir string) error {
	var merr errors.MultiError
	if paths.ControlFilesArchive != "" {
		merr = append(merr, unarchiveControlFiles(paths.ControlFilesArchive, outdir))
	}
	if paths.TestSuitesArchive != "" {
		merr = append(merr, unarchiveTestSuites(paths.TestSuitesArchive, outdir))
	}
	return unwrapMultiErrorIfNil(merr)
}

func unwrapMultiErrorIfNil(merr errors.MultiError) error {
	if merr.First() == nil {
		return nil
	}
	return merr
}

func unarchiveControlFiles(archive string, outdir string) error {
	r, err := os.Open(archive)
	if err != nil {
		return errors.Annotate(err, "unarchiveControlFiles").Err()
	}
	if err := untarAll(r, outdir); err != nil {
		return errors.Annotate(err, "unarchiveControlFiles from %s", archive).Err()
	}
	return nil
}

func unarchiveTestSuites(archive string, outdir string) error {
	r, err := os.Open(archive)
	if err != nil {
		return errors.Annotate(err, "unarchiveTestSuites").Err()
	}
	gr := bzip2.NewReader(r)
	if err := untarAll(gr, outdir); err != nil {
		return errors.Annotate(err, "unarchiveTestSuites from %s", archive).Err()
	}
	return nil
}

func untarAll(r io.Reader, outdir string) error {
	tr := tar.NewReader(r)
	for {
		h, err := tr.Next()
		switch {
		case err == io.EOF:
			// Scanned all files.
			return nil
		case err != nil:
			return errors.Annotate(err, "untarMatching").Err()
		default:
			if err := extractOne(tr, h, outdir); err != nil {
				return errors.Annotate(err, "untarMatching").Err()
			}
		}
	}
}

func extractOne(r io.Reader, h *tar.Header, outdir string) error {
	t := filepath.Join(outdir, h.Name)
	if h.FileInfo().IsDir() {
		return createDir(t)
	}
	return writeFile(r, t, h.Size)
}

func createDir(path string) error {
	return os.MkdirAll(path, 0750)
}

// writeFile writes one file of given size from a Read()er to path.
func writeFile(r io.Reader, path string, size int64) error {
	if err := createContainingDir(path); err != nil {
		return errors.Annotate(err, "writeFile").Err()
	}
	f, err := os.Create(path)
	if err != nil {
		return errors.Annotate(err, "writeFile").Err()
	}

	n, err := io.CopyN(f, r, size)
	if err != nil {
		return errors.Annotate(err, "writeFile to %s", path).Err()
	}
	if n != size {
		return errors.Reason("writeFile to %s: wrote %d bytes, want %d", path, n, size).Err()
	}
	return nil
}

func createContainingDir(path string) error {
	return createDir(filepath.Dir(path))
}
