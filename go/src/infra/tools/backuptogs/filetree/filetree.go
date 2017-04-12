package filetree

import (
	"context"
	"encoding/gob"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/luci/luci-go/common/logging"
)

// FileInfo contains metadata about a file
type FileInfo struct {
	Size    int64
	ModTime time.Time
	Mode    os.FileMode
}

// Dir is a container for other Dirs and FileInfo structs
type Dir struct {
	Files map[string]*FileInfo
	Dirs  map[string]*Dir
}

// New returns a new Dir struct
func New() *Dir {
	return &Dir{
		Files: make(map[string]*FileInfo),
		Dirs:  make(map[string]*Dir),
	}
}

// Load returns a Dir struct loaded from a file
func Load(ctx context.Context, filename string) (dir *Dir, err error) {
	var f *os.File
	f, err = os.Open(filename)
	if err != nil {
		logging.Errorf(ctx, "Failed to open file '%s': %v", filename, err)
		return nil, err
	}
	defer func() {
		if errClose := f.Close(); err != nil {
			err = errClose
			logging.Errorf(ctx, "Failed to close BackupState file '%s': %v", filename, err)
		}
	}()

	dir = New()
	dec := gob.NewDecoder(f)
	if err := dec.Decode(dir); err != nil {
		logging.Errorf(ctx, "Failed to decode BackupState from file '%s': %v", filename, err)
		return nil, err
	}

	return dir, err // err can still potentially become non-nil in deferred func that closes the file.
}

// Get returns the FileInfo at the given path.
// If it doesn't exist, it returns nil
func (d *Dir) Get(path string) *FileInfo {
	return d.get(splitPath(path))
}

func (d *Dir) get(pathParts []string) *FileInfo {
	// If Path is in this Dir
	if len(pathParts) == 1 {
		if f, ok := d.Files[pathParts[0]]; ok {
			return f
		}
		return nil
	}

	// Else, File is in a subdir
	if subdir, ok := d.Dirs[pathParts[0]]; ok {
		return subdir.get(pathParts[1:])
	}

	// Else it wasn't found
	return nil
}

// GetAllPaths returns a channel that will be populated with every path within the Directory
// The channel will be closed after all paths have been written.
func (d *Dir) GetAllPaths(ctx context.Context) <-chan string {
	paths := make(chan string, 10)

	go func() {
		d.getAllPaths(ctx, paths, "")
		close(paths)
	}()

	return paths
}

func (d *Dir) getAllPaths(ctx context.Context, paths chan<- string, prefix string) {
	for subdir := range d.Dirs {
		d.Dirs[subdir].getAllPaths(ctx, paths, prefix+subdir)
	}

	for f := range d.Files {
		select {
		case _ = <-ctx.Done():
			return
		default:
		}
		paths <- prefix + f
	}
}

// Put stores the FileInfo at the given path
func (d *Dir) Put(path string, f *FileInfo) {
	d.put(splitPath(path), f)
}

func (d *Dir) put(pathParts []string, f *FileInfo) {
	// Put file in this Dir
	if len(pathParts) == 1 {
		d.Files[pathParts[0]] = f
		return
	}

	// Else, Put file in a subdir
	subdir, ok := d.Dirs[pathParts[0]]
	if !ok {
		subdir = New()
		d.Dirs[pathParts[0]] = subdir
	}
	subdir.put(pathParts[1:], f)

}

// Del deletes the FileInfo stored at path, if it exists.
func (d *Dir) Del(path string) {
	d.del(splitPath(path))
}

func (d *Dir) del(pathParts []string) {
	// Delete file in this dir
	if len(pathParts) == 1 {
		delete(d.Files, pathParts[0])
		return
	}

	// Else, delete file in a subdir
	// Also delete the subdir if it's now empty
	if subdir, ok := d.Dirs[pathParts[0]]; ok {
		subdir.del(pathParts[1:])
		if subdir.empty() {
			delete(d.Dirs, pathParts[0])
		}
	}
}

func (d *Dir) empty() bool {
	return len(d.Files)+len(d.Dirs) == 0
}

// MatchOsInfo checks whether the given path in the Directory matches
// the file info in the provided os.FileInfo.
// true is returned if the path exists and it matches the Size, ModTime and Mode of the
// provided os.FileInfo
// Otherwise, false is returned.
func (d *Dir) MatchOsInfo(path string, info os.FileInfo) bool {
	prev := d.Get(path)
	// If we found the file and all these things match, the file isn't considered different
	return (prev != nil &&
		prev.Size == info.Size() &&
		prev.ModTime == info.ModTime() &&
		prev.Mode == info.Mode())
}

// Save serializes the Directory struct to a file.
// The Directory data can be recovered using the Load function.
func (d *Dir) Save(ctx context.Context, filename string) error {
	f, err := os.Create(filename)
	if err != nil {
		logging.Errorf(ctx, "Failed to open file '%s' for writing: %v", filename, err)
		return err
	}

	enc := gob.NewEncoder(f)
	err = enc.Encode(d)
	if err != nil {
		logging.Errorf(ctx, "Failed to encode BackupState to file: %v", err)
		return err
	}

	if err := f.Close(); err != nil {
		logging.Errorf(ctx, "Failed to close file where BackupState was saved: %v", err)
		return err
	}

	return nil
}

func splitPath(path string) []string {
	return strings.SplitAfter(path, string(filepath.Separator))
}
