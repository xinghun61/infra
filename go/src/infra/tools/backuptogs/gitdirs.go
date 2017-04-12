package main

import (
	"bufio"
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/tsmon/field"
	"github.com/luci/luci-go/common/tsmon/metric"
	"github.com/luci/luci-go/common/tsmon/types"
)

const (
	gitCommand = "git"
)

var (
	gitStatusDuration = metric.NewFloat(
		"backups/git_status_duration",
		"Time spent finding changed files in a git directory",
		&types.MetricMetadata{Units: types.Seconds},
		field.String("git_dir"))
	gitChangedFilesCount = metric.NewInt(
		"backups/git_changed_files",
		"Number of files in git directories that were explicitly backed up",
		&types.MetricMetadata{},
		field.String("git_dir"))
)

// isGitRepoDir determines whether <path> contains a git repository
func isGitRepoDir(path string) (bool, error) {
	f, err := os.Open(filepath.Join(path, ".git"))
	if err != nil {
		if os.IsNotExist(err) {
			return false, nil
		}
		return false, err
	}
	info, err := f.Stat()
	if err != nil {
		return false, err
	}

	return info.IsDir(), nil
}

// listGitChangedFiles generates a list of "changed files" in a git directory
// "Changed files" is determined by the command "git status --porcelain",
// but excludes deleted files (prefix = " D ")
// typical lines from "git status --porcelain" look like:
// !! path/to/file/within/git/repo
// ?? path2/to/file2/within/git/repo
//  M somepath
//  D this/file/has/been/deleted
func listGitChangedFiles(ctx context.Context, gitDir string) ([]string, error) {
	start := time.Now()
	defer func() {
		gitStatusDuration.Set(ctx, time.Since(start).Seconds(), gitDir)
	}()

	var changedFiles []string

	gitCmd := exec.CommandContext(ctx,
		gitCommand,
		"-C", gitDir, // Apply the command to the git repository at <gitDir>
		"status", "--porcelain", // Print "porcelain" status
	)
	output, err := gitCmd.Output()

	if err != nil {
		if exitError, ok := err.(*exec.ExitError); ok {
			logging.Debugf(ctx, "stderr from git command was '%s'", exitError.Stderr)
		}
		return nil, fmt.Errorf("error running '%s' with args '%s': %v", gitCmd.Path, gitCmd.Args, err)
	}

	lines := bufio.NewScanner(bytes.NewReader(output))

	for lines.Scan() {
		line := lines.Text()

		// skip Deleted files
		if strings.HasPrefix(line, " D ") {
			logging.Debugf(ctx, "Ignoring 'deleted file': '%s'", line)
			continue
		}

		// status code and padding is 3 chars long
		fileName := line[3:]
		changedFiles = append(changedFiles, fileName)
	}

	gitChangedFilesCount.Set(ctx, int64(len(changedFiles)), gitDir)

	return changedFiles, err
}

// processGitDirs finds "changed" files in each gitDir read from gitDirsChan
//
// It writes the names of changed files to changedFilesChan
// It is designed to be run as a goroutine
// Git errors may occur if a gitDir isn't recognised by the underlying git command.
// These errors aren't considered fatal.
func processGitDirs(ctx context.Context, gitDirsChan <-chan string, findChanged bool, errorChan chan<- error) <-chan fileInfo {
	changedFilesChan := make(chan fileInfo, 10)

	go func() {
		defer func() {
			logging.Debugf(ctx, "closing filesChan")
			close(changedFilesChan)
		}()

		for dir := range gitDirsChan {

			select {
			case _ = <-ctx.Done():
				continue
			default:
			}

			if findChanged {
				changed, err := listGitChangedFiles(ctx, dir)
				if err != nil {
					logging.Warningf(ctx, "Error while finding changed files in git dir: %v", err)
					continue // If git error, just skip this git dir and continue - git errors may occur, but aren't fatal to the overall backup process.
				}

				for _, c := range changed {
					info, err := os.Lstat(c)
					if err != nil {
						if os.IsNotExist(err) {
							continue
						}
						errorChan <- fmt.Errorf("Error stat-ing file '%s': %v", c, err)
						continue
					}
					changedFilesChan <- fileInfo{c, info}
				}
			}
		}

		logging.Debugf(ctx, "gitDirsChan closed")
	}()

	return changedFilesChan
}
