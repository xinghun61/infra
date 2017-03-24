package main

import (
	"bufio"
	"bytes"
	"context"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/tsmon"
	"github.com/luci/luci-go/common/tsmon/field"
	"github.com/luci/luci-go/common/tsmon/metric"
	"github.com/luci/luci-go/common/tsmon/types"
)

const (
	gitCommand = "/usr/bin/git"
)

var (
	findGitDirsDuration = metric.NewFloat(
		"backups/find_git_dirs_duration",
		"Time spent searching for git directories",
		&types.MetricMetadata{Units: types.Seconds},
		field.String("dir"))
	gitDirsIgnoredCount = metric.NewInt(
		"backups/git_dirs_ignored_count",
		"Number of git dirs ignored when backing up the directory",
		&types.MetricMetadata{},
		field.String("dir"))
	gitStatusDuration = metric.NewFloat(
		"backups/git_status_duration",
		"Time spent finding changed files in a git directory",
		&types.MetricMetadata{Units: types.Seconds},
		field.String("dir"),
		field.String("git_dir"))
	gitChangedFilesCount = metric.NewInt(
		"backups/git_changed_files_count",
		"Number of files in git directories that were explictily backed up",
		&types.MetricMetadata{},
		field.String("dir"),
		field.String("git_dir"))
)

// findGitDirs walks the directory tree rooted at <dir> and finds
// directories that contain a directory called ".git", writing them to <out>
// The procedure terminates immediately upon any error, or if the ctx is closed.
func findGitDirs(ctx context.Context, dir string, out chan string, errorChan chan<- error) {
	start := time.Now()
	defer func() {
		findGitDirsDuration.Set(ctx, time.Since(start).Seconds(), dir)
		if err := tsmon.Flush(ctx); err != nil {
			logging.Errorf(ctx, "Failed to flush tsmon: %v", err)
		}
	}()

	defer func() {
		close(out)
		errorChan <- nil
	}()

	var gitDirsCount int64
	err := filepath.Walk(dir, func(dir string, info os.FileInfo, err error) error {
		// Catch "file not found" errors and return nil instead.
		// File not found is acceptable, it just means the file was deleted
		// sometime between reading the directory list and getting round to stat-ing the file
		if os.IsNotExist(err) {
			logging.Warningf(ctx, "File not found: %s", dir)
			return nil
		}

		select {
		case _ = <-ctx.Done():
			logging.Warningf(ctx, "Cancelled by context")
			return ctx.Err()
		default:
			if filepath.Base(dir) == ".git" && info.IsDir() {
				out <- strings.TrimSuffix(dir, ".git")
				gitDirsCount++
			}

			return err
		}
	})

	if err != nil {
		logging.Errorf(ctx, "Error occurred during file walk: %v", err)
		errorChan <- err
		return
	}

	gitDirsIgnoredCount.Set(ctx, gitDirsCount, dir)
}

// findGitChangedFiles generates a list of "changed files" in a git directory
// "Changed files" is determined by the command "git status --porcelain",
// but excludes deleted files (prefix = " D ")
// typical lines from "git status --porcelain" look like:
// !! path/to/file/within/git/dir
// ?? path2/to/file2/within/git/dir
//  M somepath
func findGitChangedFiles(ctx context.Context, dir, gitDir string) ([]string, error) {
	start := time.Now()
	defer func() {
		gitStatusDuration.Set(ctx, time.Since(start).Seconds(), dir, gitDir)
		if err := tsmon.Flush(ctx); err != nil {
			logging.Errorf(ctx, "Failed to flush tsmon: %v", err)
		}
	}()

	var changedFiles []string

	gitCmd := exec.CommandContext(ctx, gitCommand, "-C", gitDir, "status", "--porcelain")
	output, err := gitCmd.Output()

	if err != nil {
		logging.Errorf(ctx, "Error running '%s' with args '%s': %v", gitCmd.Path, gitCmd.Args, err)
		if exitError, ok := err.(*exec.ExitError); ok {
			logging.Errorf(ctx, "stderr from git command was '%s'", exitError.Stderr)
		}

		return nil, err
	}

	// discard the status code at the start of each line
	lines := bufio.NewScanner(bytes.NewReader(output))
	for lines.Scan() {
		line := lines.Text()

		// skip Deleted files
		if strings.HasPrefix(line, " D ") {
			continue
		}

		// status code and padding is 3 chars long
		fileName := lines.Text()[3:]
		changedFiles = append(changedFiles, fileName)
	}

	gitChangedFilesCount.Set(ctx, int64(len(changedFiles)), dir)
	if err := tsmon.Flush(ctx); err != nil {
		logging.Errorf(ctx, "Failed to flush tsmon: %v", err)
	}

	return changedFiles, err
}

// streamGitChangedFiles finds "changed" files in each gitDir read from from <gitDirsChan>
// It stream's the filenames (full paths, separated by "\n") to <out>
func streamGitChangedFiles(ctx context.Context, dir string, gitDirsChan chan string, out *io.PipeWriter, errorChan chan<- error) {
	buf := bufio.NewWriter(out)

	// err can be set by many parts of the code in the main body of the function
	// it is used in the defer to determine whether to call out.CloseWithError()
	// rather than out.Close()
	var err error

	defer func() {
		if err != nil {
			errorChan <- err
		}

		if bufErr := buf.Flush(); bufErr != nil {
			logging.Errorf(ctx, "Failed to flush buffer: %v", err)
			errorChan <- bufErr
			err = bufErr
		}

		if err != nil {
			out.CloseWithError(err)
		} else if err := out.Close(); err != nil {
			logging.Errorf(ctx, "Failed to close output pipe: %v", err)
			errorChan <- err
		}

		errorChan <- nil
	}()

	for gitDir := range gitDirsChan {
		select {
		case _ = <-ctx.Done():
			logging.Errorf(ctx, "Cancelled by context")
			err = ctx.Err()
			return
		default:
			var changed []string
			changed, err = findGitChangedFiles(ctx, dir, gitDir)
			if err != nil {
				logging.Errorf(ctx, "Error while finding changed files in git dir '%s': %v", gitDir, err)
				return
			}

			for _, c := range changed {
				if _, err = buf.WriteString(gitDir + c + "\n"); err != nil {
					logging.Errorf(ctx, "Failed to write filename to output pipe ('%s' from git dir '%s'): %v", c, gitDir, err)
					return
				}
			}
		}
	}
}
