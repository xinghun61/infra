package main

import (
	"context"
	"fmt"
	"os"

	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/logging/gologger"
	"github.com/luci/luci-go/common/tsmon"
	"github.com/luci/luci-go/common/tsmon/metric"
	"github.com/luci/luci-go/common/tsmon/types"
)

type gitMode int

const (
	gitModeKeep gitMode = iota
	gitModeSkip
	gitModeChanged
)

var (
	gitModes = map[string]gitMode{
		"keep":    gitModeKeep,
		"skip":    gitModeSkip,
		"changed": gitModeChanged,
	}
)

var (
	success = metric.NewBool("backups/success",
		"Whether or not the backup completed successfully",
		&types.MetricMetadata{})
)

// error codes returned by the process
const (
	optionsError int = iota
	tsmonError
	jobError
	backupError
	saveStateError
)

func main() {
	ctx := context.Background()

	// Create options
	opts, err := newOptionsFromArgs(os.Args[1:])
	if err != nil {
		fmt.Printf("Failed to initialize options: %v", err)
		os.Exit(optionsError)
	}

	// Init Logging
	ctx = gologger.StdConfig.Use(ctx)
	ctx = opts.loggingConfig.Set(ctx)

	// Init Tsmon
	if err := tsmon.InitializeFromFlags(ctx, &opts.tsmonFlags); err != nil {
		logging.Errorf(ctx, "Failed to initialize tsmon: %v", err)
		os.Exit(tsmonError)
	}
	defer func() {
		if err := tsmon.Flush(ctx); err != nil {
			logging.Errorf(ctx, "Failed to flush tsmon: %v", err)
		}
		tsmon.Shutdown(ctx)
	}()

	// Init backup job
	job, err := opts.makeJob(ctx)
	if err != nil {
		logging.Errorf(ctx, "Failed to make job from options: %v", err)
		os.Exit(jobError)
	}

	logging.Infof(ctx, "Starting backup of '%s' to bucket '%s' using name prefix '%s'",
		opts.root, opts.bucket, opts.prefix)

	// Run the backup
	state, err := job.run(ctx)
	if err != nil {
		logging.Errorf(ctx, "Backup failed: %v", err)
		os.Exit(backupError)
	}

	// Save backup state
	if opts.newState != "" {
		if err = state.Save(ctx, opts.newState); err != nil {
			logging.Errorf(ctx, "Failed to save Backup State to file: %v", err)
			os.Exit(saveStateError)
		}
	}

	success.Set(ctx, true)

	logging.Infof(ctx, "Finished backup of '%s' to bucket '%s' using name prefix '%s'",
		opts.root, opts.bucket, opts.prefix)
}
