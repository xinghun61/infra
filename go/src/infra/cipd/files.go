// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"io"
	"os"
	"path/filepath"
)

// File defines a single file to be added or extracted from a package.
type File interface {
	// Slash separated file path, relative to a package root, e.g. "dir/dir/file".
	Name() string
	// Size of the file.
	Size() uint64
	// Is the file executable? Only used for Linux\Mac archives.
	Executable() bool
	// Open the file for reading.
	Open() (io.ReadCloser, error)
}

////////////////////////////////////////////////////////////////////////////////
// File system source.

type fileSystemFile struct {
	absPath    string
	name       string
	size       uint64
	executable bool
}

func (f *fileSystemFile) Name() string                 { return f.name }
func (f *fileSystemFile) Size() uint64                 { return f.size }
func (f *fileSystemFile) Executable() bool             { return f.executable }
func (f *fileSystemFile) Open() (io.ReadCloser, error) { return os.Open(f.absPath) }

// ScanFileSystem returns all files in some file system directory in
// an alphabetical order. It returns only files, skipping directory entries
// (i.e. empty directories are complete invisible). ScanFileSystem does not
// follow and does not recognize symbolic links.
func ScanFileSystem(root string) ([]File, error) {
	root, err := filepath.Abs(filepath.Clean(root))
	if err != nil {
		return nil, err
	}

	files := []File{}

	err = filepath.Walk(root, func(abs string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(root, abs)
		if err != nil {
			return err
		}
		if info.Mode().IsRegular() {
			files = append(files, &fileSystemFile{
				absPath:    abs,
				name:       filepath.ToSlash(rel),
				size:       uint64(info.Size()),
				executable: (info.Mode().Perm() & 0111) != 0,
			})
		}
		return nil
	})

	if err != nil {
		return nil, err
	}
	return files, nil
}
