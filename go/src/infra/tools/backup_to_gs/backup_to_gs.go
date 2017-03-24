package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"cloud.google.com/go/storage"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/logging/gologger"
	"github.com/luci/luci-go/common/tsmon"
	"github.com/luci/luci-go/common/tsmon/field"
	"github.com/luci/luci-go/common/tsmon/metric"
	"github.com/luci/luci-go/common/tsmon/target"
	"github.com/luci/luci-go/common/tsmon/types"
	"google.golang.org/api/option"
)

const tarCommand = "/bin/tar"

var (
	runDuration = metric.NewFloat("backups/duration",
		"Time taken to run the backups",
		&types.MetricMetadata{Units: types.Seconds},
		field.String("dir"))
	archiveSize = metric.NewInt("backups/archive_size",
		"Size in bytes of the archive",
		&types.MetricMetadata{Units: types.Bytes},
		field.String("dir"))
	success = metric.NewBool("backups/success",
		"Whether or not the backup completed successfully",
		&types.MetricMetadata{},
		field.String("dir"))
)

func newGSWriter(ctx context.Context, bucket, name, credsfile string) (*storage.Writer, error) {
	client, err := storage.NewClient(ctx, option.WithServiceAccountFile(credsfile))
	if err != nil {
		logging.Errorf(ctx, "Failed to create new GCS client: %v", err)
		return nil, err
	}

	bkt := client.Bucket(bucket)
	obj := bkt.Object(name)

	return obj.NewWriter(ctx), nil
}

func runTar(ctx context.Context, dir string, extraFiles *io.PipeReader, out io.WriteCloser, errorChan chan<- error) {
	var err error

	defer func() {
		if err != nil {
			errorChan <- err
		}

		if outErr := out.Close(); outErr != nil {
			logging.Errorf(ctx, "Failed to close output stream: %v", outErr)
			errorChan <- outErr
			err = outErr
		}

		if err != nil {
			extraFiles.CloseWithError(err)
		} else if err := extraFiles.Close(); err != nil {
			logging.Errorf(ctx, "Failed to close output stream: %v", err)
			errorChan <- err
		}

		errorChan <- nil
	}()

	tarArgs := []string{
		"-cjv", // create a new archive, bzip2 compression, verbose output
		"--exclude-tag-all=.git", // ignore directories containing .git
		"--files-from=-",         // read list of file targets from stdin
		dir,
	}
	tarCmd := exec.CommandContext(ctx, tarCommand, tarArgs...)
	tarCmd.Stdin = extraFiles
	tarCmd.Stdout = out

	// FIXME capture stderr somehow and get messages from it.

	err = tarCmd.Run()

	// Check if exit code was 1 - if so, print warning and set err to nil instead.
	if err != nil {
		logging.Warningf(ctx, "Tar process returned error: %v", err)
		if exitError, ok := err.(*exec.ExitError); ok {
			if status, ok := exitError.ProcessState.Sys().(syscall.WaitStatus); ok {
				logging.Warningf(ctx, "Tar return code was %d", status.ExitStatus())
				if status.ExitStatus() == 1 {
					logging.Warningf(ctx, "Exit code 1 indicates file contents changed during backup.")
					err = nil
				}
			}

		}
	}
}

func backupDir(ctx context.Context, dir, bucket, dest, creds string) {
	// Time the duration of this backup run and send to monitoring
	start := time.Now()
	defer func() {
		runDuration.Set(ctx, time.Since(start).Seconds(), dir)
		if err := tsmon.Flush(ctx); err != nil {
			logging.Errorf(ctx, "Failed to flush tsmon: %v", err)
		}
	}()

	// Make sub-context that will be passed to members of the main backup pipeline
	// cancelPipeline() is used to shutdown all members of the pipeline.
	pipelineCtx, cancelPipeline := context.WithCancel(ctx)
	defer cancelPipeline()

	logging.Infof(pipelineCtx, "Backing up dir '%s' to bucket '%s' using name '%s'",
		dir, bucket, dest)

	gsWriter, err := newGSWriter(pipelineCtx, bucket, dest, creds)
	if err != nil {
		panic(fmt.Sprintf("Failed to create new GCS client: %v", err))
	}
	defer func() {
		if err := gsWriter.Close(); err != nil {
			logging.Errorf(pipelineCtx, "Failed to close GCS client: %v", err)
			return
		}

		archiveSize.Set(pipelineCtx, gsWriter.Attrs().Size, dir)
		if err := tsmon.Flush(pipelineCtx); err != nil {
			logging.Errorf(pipelineCtx, "Failed to flush tsmon: %v", err)
		}
	}()

	// errorChan is written to by all three goroutines below
	// In addition to any actual errors written to errorChan,
	// each goroutine will send a single nil when they exit.
	// The goroutines must never send more than one nil.
	errorChan := make(chan error)

	// Find git dirs
	gitDirsOutputChan := make(chan string, 10)
	go findGitDirs(pipelineCtx, dir, gitDirsOutputChan, errorChan)

	// Find changed files in git dirs
	extraPathsReader, extraPathsWriter := io.Pipe()
	go streamGitChangedFiles(pipelineCtx, dir, gitDirsOutputChan, extraPathsWriter, errorChan)

	// tar up everything in dir and send to 'gsWriter'
	// Exclude .git directories, but include any filepaths read from
	// 'extraPathsReader'
	go runTar(pipelineCtx, dir, extraPathsReader, gsWriter, errorChan)

	// Wait for completion of all goroutines.
	// Any errors from any goroutine cause the context to be cancelled.
	// A value of nil on the error channel indicates that one of the goroutines
	// has finished.
	// Iteration continues until all 'nil' values have been received
	ok := true
	for nilCount := 0; nilCount < 3; {
		if err := <-errorChan; err != nil {
			logging.Errorf(pipelineCtx, "Error returned by a goroutine: %v", err)
			cancelPipeline()
			ok = false
		} else {
			nilCount++
		}
	}

	success.Set(pipelineCtx, ok, dir)

	logging.Infof(pipelineCtx, "Finished backup run for dir '%s': Success = %t", dir, ok)
}

func main() {
	// Initialise flags, logging and ts-mon
	fs := flag.NewFlagSet("", flag.ExitOnError)

	flags := NewFlags()
	flags.Register(fs)

	tsmonFlags := tsmon.NewFlags()
	tsmonFlags.Flush = tsmon.FlushManual
	tsmonFlags.Target.TargetType = target.TaskType
	tsmonFlags.Target.TaskServiceName = "backups"
	tsmonFlags.Register(fs)

	loggingConfig := logging.Config{Level: logging.Info}
	loggingConfig.AddFlags(fs)

	fs.Parse(os.Args[1:])

	ctx := context.Background()
	ctx = gologger.StdConfig.Use(ctx)
	ctx = loggingConfig.Set(ctx)

	if err := tsmon.InitializeFromFlags(ctx, &tsmonFlags); err != nil {
		panic(fmt.Sprintf("Failed to initialize tsmon: %v", err))
	}
	defer tsmon.Shutdown(ctx)

	for _, dir := range filepath.SplitList(flags.dirs) {
		dest := filepath.Join(flags.dest, dir)
		dest = strings.TrimRight(dest, "/")
		dest += ".tar.bz2"
		backupDir(ctx, dir, flags.bucket, dest, flags.serviceAccountCreds)
	}
}
