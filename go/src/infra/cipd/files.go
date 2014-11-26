// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"fmt"
	"io"
	"io/ioutil"
	"os"
	"path/filepath"
)

// File defines a single file to be added or extracted from a package.
type File interface {
	// Name returns slash separated file path relative to a package root, e.g. "dir/dir/file".
	Name() string
	// Size returns size of the file.
	Size() uint64
	// Executable returns true if the file is executable. Only used for Linux\Mac archives.
	Executable() bool
	// Open opens the file for reading.
	Open() (io.ReadCloser, error)
}

// Destination knows how to create files when extracting a package. It supports
// transactional semantic by providing 'Begin' and 'End' methods. No changes
// should be applied until End(true) is called. A call to End(false) should
// discard any pending changes.
type Destination interface {
	// Begin initiates a new write transaction. Called before first CreateFile.
	Begin() error
	// CreateFile opens a writer to extract some package file to.
	CreateFile(name string, executable bool) (io.WriteCloser, error)
	// End finalizes package extraction (commit or rollback, based on success).
	End(success bool) error
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

////////////////////////////////////////////////////////////////////////////////
// FileSystemDestination implementation.

type fileSystemDestination struct {
	// Destination directory.
	dir string
	// Root temporary directory.
	tempDir string
	// Where to extract all temp files, subdirectory of tempDir.
	outDir string
	// Currently open files.
	openFiles map[string]*os.File
}

// NewFileSystemDestination returns a destination in the file system (directory)
// to extract a package to.
func NewFileSystemDestination(dir string) Destination {
	return &fileSystemDestination{
		dir:       dir,
		openFiles: make(map[string]*os.File),
	}
}

func (d *fileSystemDestination) Begin() (err error) {
	if d.tempDir != "" {
		return fmt.Errorf("Destination is already open")
	}

	// Ensure parent directory of destination directory exists.
	d.dir, err = filepath.Abs(filepath.Clean(d.dir))
	if err != nil {
		return err
	}
	err = os.MkdirAll(filepath.Dir(d.dir), 0777)
	if err != nil {
		return err
	}

	// Called in case something below fails.
	cleanup := func() {
		if d.tempDir != "" {
			os.RemoveAll(d.tempDir)
		}
		d.tempDir = ""
		d.outDir = ""
	}

	// Create root temp dir, on the same level as destination directory.
	d.tempDir, err = ioutil.TempDir(filepath.Dir(d.dir), filepath.Base(d.dir)+"_")
	if err != nil {
		cleanup()
		return err
	}

	// Create a staging output directory where everything will be extracted.
	d.outDir = filepath.Join(d.tempDir, "out")
	err = os.MkdirAll(d.outDir, 0777)
	if err != nil {
		cleanup()
		return err
	}

	return nil
}

func (d *fileSystemDestination) CreateFile(name string, executable bool) (io.WriteCloser, error) {
	if d.tempDir == "" {
		return nil, fmt.Errorf("Destination is not open")
	}

	path := filepath.Join(d.outDir, filepath.FromSlash(name))
	if !filepath.IsAbs(path) {
		return nil, fmt.Errorf("Invalid relative file name: %s", name)
	}

	_, ok := d.openFiles[name]
	if ok {
		return nil, fmt.Errorf("File %s is already open", name)
	}

	// Make sure full path exists.
	err := os.MkdirAll(filepath.Dir(path), 0777)
	if err != nil {
		return nil, err
	}

	// Let the umask trim the file mode. Do not set 'writable' bit though.
	var mode os.FileMode
	if executable {
		mode = 0555
	} else {
		mode = 0444
	}

	file, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_EXCL, mode)
	if err != nil {
		return nil, err
	}
	d.openFiles[name] = file
	return &fileSystemDestinationFile{
		nested: file,
		parent: d,
		closeCallback: func() {
			delete(d.openFiles, name)
		},
	}, nil
}

func (d *fileSystemDestination) End(success bool) error {
	if d.tempDir == "" {
		return fmt.Errorf("Destination is not open")
	}
	if len(d.openFiles) != 0 {
		return fmt.Errorf("Not all files were closed. Leaking.")
	}

	// Clean up temp dir and the state no matter what.
	defer func() {
		os.RemoveAll(d.tempDir)
		d.tempDir = ""
		d.outDir = ""
	}()

	if success {
		// Move existing directory away, if it is there.
		old := filepath.Join(d.tempDir, "old")
		if os.Rename(d.dir, old) != nil {
			old = ""
		}

		// Move new directory in place.
		err := os.Rename(d.outDir, d.dir)
		if err != nil {
			// Try to return the original directory back...
			if old != "" {
				os.Rename(old, d.dir)
			}
			return err
		}
	}

	return nil
}

type fileSystemDestinationFile struct {
	nested        io.WriteCloser
	parent        *fileSystemDestination
	closeCallback func()
}

func (f *fileSystemDestinationFile) Write(p []byte) (n int, err error) {
	return f.nested.Write(p)
}

func (f *fileSystemDestinationFile) Close() error {
	f.closeCallback()
	return f.nested.Close()
}
