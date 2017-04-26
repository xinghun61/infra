package main

import (
	"context"
	"time"

	"infra/tools/backuptogs/filetree"

	"cloud.google.com/go/storage"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/tsmon/metric"
	"github.com/luci/luci-go/common/tsmon/types"
)

var (
	runDuration = metric.NewFloat("backups/duration",
		"Time taken to run the backups",
		&types.MetricMetadata{Units: types.Seconds})
)

// job contains values and objects needed to perform a backup job
type job struct {
	root       string
	exclusions []string
	gitMode    gitMode
	oneFs      bool
	bucket     *storage.BucketHandle
	prefix     string
	key        []byte
	prevState  *filetree.Dir
	workers    int
}

// run performs a backup run
//
// If backup was successful, the backup state is returned as a *filetree.Dir
// The state represents every file that was seen locally, rather than files that were actually backed up,
// ie it includes files that were skipped because they hadn't changed compared to the previous state
func (j *job) run(ctx context.Context) (*filetree.Dir, error) {
	// Time the backup run
	start := time.Now()
	defer func() {
		runDuration.Set(ctx, time.Since(start).Seconds())
	}()

	logging.Debugf(ctx, "Starting backup pipeline")
	// backup files to GCS
	newState, err := j.backupFiles(ctx)
	if err != nil {
		return nil, err
	}

	if j.prevState != nil {
		logging.Debugf(ctx, "Starting deletion pipeline")
		// delete files from GCS
		if err = j.delFiles(ctx); err != nil {
			return nil, err
		}
	}

	return newState, nil
}

// backupFiles backs up files from the local filesystem to GCS
func (j *job) backupFiles(ctx context.Context) (*filetree.Dir, error) {
	pipelineCtx, cancelPipeline := context.WithCancel(ctx)
	defer cancelPipeline()

	// errorChan is used by many pipeline stages below
	// any non-nil error on errorChan is considered fatal and will cause the
	// context to be cancelled and the pipeline will be shutdown.
	errorChan := make(chan error)

	// Start the pipeline
	// Each function starts one or more goroutines, and returns read-only channels where
	// their results are written
	// The result channels are passed to subsequent stages of the processing pipeline
	// The result channels are closed when a goroutine has finished all work.
	skipGit := j.gitMode == gitModeChanged || j.gitMode == gitModeSkip
	filesSeenChan, gitDirsChan := walkFilesystem(pipelineCtx, j.root, j.exclusions, j.oneFs, skipGit, errorChan)

	findGitChanged := j.gitMode == gitModeChanged
	gitFilesChan := processGitDirs(pipelineCtx, gitDirsChan, findGitChanged, errorChan)

	allFilesChan := mergeFileInfoChans(filesSeenChan, gitFilesChan)

	newState := filetree.New()
	backupsChan := filterFiles(pipelineCtx, allFilesChan, j.prevState, newState)

	backupDone := backupToGS(pipelineCtx, backupsChan, j.bucket, j.prefix, j.key, j.workers, errorChan)

	// Wait for the pipeline to finish while also checking errorChan for non-nil errors
	if err := waitToFinish(ctx, backupDone, errorChan, cancelPipeline); err != nil {
		return nil, err
	}

	return newState, nil
}

func (j *job) delFiles(ctx context.Context) error {
	// Make sub-context that will be passed to each goroutine in the backup pipeline
	// cancelPipeline() is used to shutdown all members of the pipeline.
	pipelineCtx, cancelPipeline := context.WithCancel(ctx)
	defer cancelPipeline()

	errorChan := make(chan error)

	// Delete files from GCS that weren't seen during the backup phase
	filesToDeleteChan := j.prevState.GetAllPaths(pipelineCtx)
	delDone := delFromGS(pipelineCtx, j.bucket, j.prefix, filesToDeleteChan, j.workers, errorChan)

	return waitToFinish(ctx, delDone, errorChan, cancelPipeline)
}

// waitToFinish watches the pipeline represented by 'doneChan', 'errorChan' and 'cancelFunc'
//
// Any non-nil error on errorChan will cause cancelFunc to be called
// The return value is the first error seen on errorChan, or nil on success
func waitToFinish(ctx context.Context, doneChan <-chan struct{}, errorChan <-chan error, cancelFunc func()) error {
	// Wait for the pipeline to finish while also checking errorChan for non-nil errors
	var err error
	var done bool
	for !done {
		select {
		case e := <-errorChan:
			if e != nil {
				logging.Debugf(ctx, "Error from errorChan: %v", e)
				if err == nil {
					err = e
				}
				cancelFunc()
			}
		case _ = <-doneChan:
			logging.Debugf(ctx, "Pipeline finished")
			done = true
		}
	}

	return err
}
