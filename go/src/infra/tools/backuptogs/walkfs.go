package main

import (
	"context"
	"fmt"
	"os"
	"path/filepath"

	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/tsmon/metric"
	"github.com/luci/luci-go/common/tsmon/types"
)

var (
	gitDirsIgnoredCount = metric.NewCounter(
		"backups/git_dirs_ignored",
		"Number of git dirs ignored when backing up the directory",
		&types.MetricMetadata{})
)

// fileInfo contains info about a file on the local filesystem.
// Unlike os.FileInfo, it contains the full path to the file
type fileInfo struct {
	path   string
	osInfo os.FileInfo
}

// walkFilesystem generates a list of files from <root> on the local filesystem
//
// If <skipGit> is true, git directories will be skipped, but their names will bit written to gitDirsChan
func walkFilesystem(
	ctx context.Context,
	root string,
	excludePatterns []string,
	oneFs bool,
	skipGit bool,
	errorChan chan<- error) (<-chan fileInfo, <-chan string) {

	filesChan := make(chan fileInfo, 10)
	gitDirsChan := make(chan string, 10)

	go func() {
		defer func() {
			logging.Debugf(ctx, "Closing gitDirsChan")
			close(gitDirsChan)
			logging.Debugf(ctx, "Closing filesChan")
			close(filesChan)
		}()

		// Get Filesystem/Volume Id of root path of backup
		baseFs, err := getFs(ctx, root)
		if err != nil {
			errorChan <- fmt.Errorf("Failed to stat root path '%s': %v", root, err)
			return
		}

		errorChan <- filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
			// Check context
			select {
			case _ = <-ctx.Done():
				return ctx.Err()
			default:
			}

			// Abort if err != nil, except if it's File Not Found error
			if err != nil {
				if os.IsNotExist(err) {
					logging.Warningf(ctx, "File not found: '%s'", path)
					return nil
				}
				return err
			}

			// Check if file is on different filesystem/volume
			if oneFs {
				fs, err := getFs(ctx, path)
				if err != nil {
					logging.Errorf(ctx, "Failed to determine filesystem of file '%s'", path)
					return err
				}
				if fs != baseFs {
					logging.Debugf(ctx, "Not crossing filesystem at '%s'", path)
					return filepath.SkipDir
				}
			}

			// Check exclude patterns
			if exclude(path, excludePatterns) {
				return filepath.SkipDir
			}

			// Switch on file type
			// - Regular files get backed up
			// - Directories get checked for git and skipped if required
			// - Other file types are ignored
			switch {
			case info.Mode().IsRegular():
				filesChan <- fileInfo{path, info}
			case info.IsDir() && skipGit:
				isGit, err := isGitRepoDir(path)
				if err != nil {
					if os.IsNotExist(err) {
						logging.Warningf(ctx, "File not found: '%s'", path)
						return nil
					}
					return err
				}
				if isGit {
					gitDirsIgnoredCount.Add(ctx, 1)
					gitDirsChan <- path
					return filepath.SkipDir
				}
			}

			return nil
		}) // End filepath.Walk()

		logging.Debugf(ctx, "walkFilesystem has finished")
	}()

	return filesChan, gitDirsChan
}

func exclude(s string, patterns []string) bool {
	// Ignore the error returned by filepath.Match(). Any illegal patterns should have been caught during setup.
	for _, p := range patterns {
		if matched, _ := filepath.Match(p, s); matched {
			return true
		}
	}
	return false
}
