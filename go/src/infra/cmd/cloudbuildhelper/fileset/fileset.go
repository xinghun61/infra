// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package fileset contains an abstraction for a set of files.
package fileset

import (
	"archive/tar"
	"io"
	"os"
	"path"
	"path/filepath"
	"sort"
	"strings"

	"go.chromium.org/luci/common/errors"
)

// File is a file inside a file set.
type File struct {
	Path      string // file path using "/" separator
	Directory bool   // true if this is a directory

	Size       int64 // size of the file, only for regular files
	Writable   bool  // true if the file is writable, only for regular files
	Executable bool  // true if the file is executable, only for regular files

	Body func() (io.ReadCloser, error) // emits the body, only for regular files
}

// normalize clears redundant fields and converts file paths to Unix style.
//
// Returns an error if the file entry is invalid.
func (f *File) normalize() error {
	f.Path = path.Clean(filepath.ToSlash(f.Path))
	if f.Path == "." || strings.HasPrefix(f.Path, "../") {
		return errors.Reason("bad file path %q, not in the set", f.Path).Err()
	}
	if f.Directory {
		f.Size = 0
		f.Writable = false
		f.Executable = false
		f.Body = nil
	}
	return nil
}

// filePerm returns FileMode with file permissions.
func (f *File) filePerm() os.FileMode {
	var mode os.FileMode = 0400
	if f.Writable {
		mode |= 0200
	}
	if f.Executable {
		mode |= 0100
	}
	return mode
}

// Set represents a set of regular files and directories (no symlinks).
//
// Such set can be constructed from existing files on disk (perhaps scattered
// across many directories), and it then can be either materialized on disk
// in some root directory, or written into a tarball.
type Set struct {
	files map[string]File // unix-style path inside the set => File
}

// Add adds a file or directory to the set, overriding an existing one, if any.
//
// Adds all intermediary directories, if necessary.
//
// Returns an error if the file path is invalid (e.g. starts with "../"").
func (s *Set) Add(f File) error {
	if err := f.normalize(); err != nil {
		return err
	}

	if s.files == nil {
		s.files = make(map[string]File, 1)
	}

	// Add intermediary directories. Bail if some of them are already added as
	// regular files.
	cur := ""
	for _, chr := range f.Path {
		if chr == '/' {
			switch existing, ok := s.files[cur]; {
			case !ok:
				s.files[cur] = File{Path: cur, Directory: true}
			case ok && !existing.Directory:
				return errors.Reason("%q in file path %q is not a directory", cur, f.Path).Err()
			}
		}
		cur += string(chr)
	}

	// Add the leaf file.
	s.files[f.Path] = f
	return nil
}

// AddFromDisk adds a given file or directory to the set.
//
// A file or directory located at 'fsPath' on disk will become 'setPath' in
// the set. Directories are added recursively. Symlinks are always expanded into
// whatever they point to. Broken symlinks are silently skipped.
func (s *Set) AddFromDisk(fsPath, setPath string) error {
	fsPath, err := filepath.Abs(fsPath)
	if err != nil {
		return err
	}
	setPath = path.Clean(filepath.ToSlash(setPath))
	return s.addImpl(fsPath, setPath)
}

// Len returns number of files in the set.
func (s *Set) Len() int {
	return len(s.files)
}

// Enumerate calls the callback for each file in the set, in alphabetical order.
//
// Returns whatever error the callback returns.
func (s *Set) Enumerate(cb func(f File) error) error {
	names := make([]string, 0, len(s.files))
	for f := range s.files {
		names = append(names, f)
	}
	sort.Strings(names)
	for _, n := range names {
		if err := cb(s.files[n]); err != nil {
			return err
		}
	}
	return nil
}

// Files returns all files in the set, in alphabetical order.
func (s *Set) Files() []File {
	out := make([]File, 0, len(s.files))
	s.Enumerate(func(f File) error {
		out = append(out, f)
		return nil
	})
	return out
}

// Materialize dumps all files in this set into the given directory.
//
// The directory should already exist. The contents of 's' will be written on
// top of whatever is in the directory.
//
// Doesn't cleanup on errors.
func (s *Set) Materialize(root string) error {
	buf := make([]byte, 64*1024)
	return s.Enumerate(func(f File) error {
		p := filepath.Join(root, filepath.FromSlash(f.Path))
		if f.Directory {
			return os.Mkdir(p, 0700)
		}

		r, err := f.Body()
		if err != nil {
			return err
		}
		defer r.Close()

		w, err := os.OpenFile(p, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, f.filePerm())
		if err != nil {
			return err
		}
		defer w.Close() // this is for early exits, we'll also explicitly close later

		copied, err := io.CopyBuffer(w, r, buf)
		if err != nil {
			return err
		}
		if copied != f.Size {
			return errors.Reason("file %q has unexpected size (expecting %d, got %d)", f.Path, f.Size, copied).Err()
		}
		return w.Close()
	})
}

// Tarball dumps all files in this set into the tarball.
func (s *Set) Tarball(w *tar.Writer) error {
	panic("not implemented")
}

////////////////////////////////////////////////////////////////////////////////

// addImpl implements AddFromDisk.
func (s *Set) addImpl(fsPath, setPath string) error {
	switch stat, err := os.Stat(fsPath); {
	case os.IsNotExist(err):
		if _, lerr := os.Lstat(fsPath); lerr == nil {
			return nil // fsPath is a broken symlink, skip it
		}
		return err
	case err != nil:
		return err
	case stat.Mode().IsRegular():
		return s.addReg(fsPath, setPath, stat)
	case stat.Mode().IsDir():
		return s.addDir(fsPath, setPath)
	default:
		return errors.Reason("file %q has unsupported type, its mode is %s", fsPath, stat.Mode()).Err()
	}
}

// addReg adds a regular file to the set.
func (s *Set) addReg(fsPath, setPath string, fi os.FileInfo) error {
	return s.Add(File{
		Path:       setPath,
		Size:       fi.Size(),
		Writable:   (fi.Mode() & 0222) != 0,
		Executable: (fi.Mode() & 0111) != 0,
		Body:       func() (io.ReadCloser, error) { return os.Open(fsPath) },
	})
}

// addDir recursively adds a directory to the set.
func (s *Set) addDir(fsPath, setPath string) error {
	// Don't add the set root itself, it is always implied. Allowing it explicitly
	// causes complication related to dealing with ".".
	if setPath != "." {
		if err := s.Add(File{Path: setPath, Directory: true}); err != nil {
			return err
		}
	}

	f, err := os.Open(fsPath)
	if err != nil {
		return err
	}
	files, err := f.Readdirnames(-1)
	if err != nil {
		return err
	}
	f.Close()

	for _, f := range files {
		if err := s.addImpl(filepath.Join(fsPath, f), path.Join(setPath, f)); err != nil {
			return err
		}
	}

	return nil
}
