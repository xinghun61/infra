package main

import (
	"context"
	"encoding/base64"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"infra/tools/backuptogs/filetree"

	"cloud.google.com/go/storage"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/tsmon"
	"github.com/luci/luci-go/common/tsmon/target"
	"google.golang.org/api/option"
)

// options holds various options for both the main app, as well as modules like tsmon and logging
type options struct {
	tsmonFlags    tsmon.Flags
	loggingConfig logging.Config

	root      string
	exclude   string
	gitMode   string
	oneFs     bool
	bucket    string
	prefix    string
	creds     string
	key       string
	prevState string
	newState  string
	workers   int
}

func newOptionsFromArgs(args []string) (*options, error) {
	opts := &options{
		tsmonFlags: tsmon.NewFlags(),
	}

	fs := flag.NewFlagSet("", flag.ExitOnError)
	opts.registerFlags(fs)
	fs.Parse(args)

	// Check exactly 1 argument left after parsing args
	args = fs.Args()
	if len(args) != 1 {
		fs.PrintDefaults()
		return nil, fmt.Errorf("exactly 1 argument required after flags: got %d args (%v)", len(args), args)
	}
	opts.root = args[0]

	return opts, nil
}

func (o *options) registerFlags(fs *flag.FlagSet) {
	// tsmon
	o.tsmonFlags = tsmon.NewFlags()
	o.tsmonFlags.Flush = tsmon.FlushAuto
	o.tsmonFlags.Target.TargetType = target.TaskType
	o.tsmonFlags.Target.TaskServiceName = "backuptogs"
	o.tsmonFlags.Target.TaskJobName = "backuptogs"
	o.tsmonFlags.Register(fs)

	// logging
	o.loggingConfig.Level = logging.Info
	o.loggingConfig.AddFlags(fs)

	// backuptogs
	fs.StringVar(&o.exclude, "exclude", "", "List of PATTERNs for paths to exclude from backups, delimited by ':'. Each PATTERN is a shell glob.")
	fs.StringVar(&o.gitMode, "gitmode", "keep", "Controls handling of git directories encountered within the backup target.\n"+
		"'keep' means git directories are treated like any other directory and backed up in their entirety.\n"+
		"'skip' means git directories are skipped.\n"+
		"'changed' means git directories are ignored, but 'changed' files within the git directory are explicitly backed up.")
	fs.BoolVar(&o.oneFs, "onefs", true, "Do not traverse filesystems.")
	fs.StringVar(&o.bucket, "bucket", "", "Bucket where backup should be stored")
	fs.StringVar(&o.prefix, "prefix", "", "Prefix to add to names of objects before writing to GCS")
	fs.StringVar(&o.creds, "creds", "", "Location of credentials file for Google Cloud Storage")
	fs.StringVar(&o.key, "key", "", "Location of encryption key file for Google Cloud Storage")
	fs.StringVar(&o.prevState, "prevstate", "", "Location of backupState file from a previous run."+
		"If provided, the backup will run as an incremental backup from the previous state")
	fs.StringVar(&o.newState, "newstate", "", "if backup is successful, backup state will be written to this file")
	fs.IntVar(&o.workers, "workers", 10, "number of file uploaders to run in parallel")
}

// makeJob validates values in o and creates a corresponding job
func (o *options) makeJob(ctx context.Context) (j *job, err error) {
	j = &job{}
	// Populate params, validating along the way
	// backup root
	j.root = o.root

	// exclusion patterns
	j.exclusions = filepath.SplitList(o.exclude)
	for _, ex := range j.exclusions {
		if _, err = filepath.Match("", ex); err != nil {
			return nil, fmt.Errorf("invalid pattern in -exclude flag: '%s'", ex)
		}
	}

	// git mode
	var ok bool
	if j.gitMode, ok = gitModes[o.gitMode]; !ok {
		return nil, fmt.Errorf("invalid value for -gitmode flag: '%s'", o.gitMode)
	}

	// fs mode
	j.oneFs = o.oneFs

	// bucket
	client, err := storage.NewClient(ctx, option.WithServiceAccountFile(o.creds))
	if err != nil {
		return nil, fmt.Errorf("failed to create new GCS client: %v", err)
	}
	j.bucket = client.Bucket(o.bucket)

	// prefix
	j.prefix = o.prefix

	// encryption key
	if o.key != "" {
		key, err := readKey(o.key)
		if err != nil {
			return nil, fmt.Errorf("failed to read encryption key from file '%s': %v", o.key, err)
		}
		j.key = key
	}

	// prevState
	if o.prevState != "" {
		state, err := filetree.Load(ctx, o.prevState)
		if err != nil {
			return nil, fmt.Errorf("failed to get previous backup state: %v", err)
		}
		j.prevState = state
	}

	// workers
	j.workers = o.workers

	return j, nil
}

func readKey(file string) (key []byte, err error) {
	f, err := os.Open(file)
	if err != nil {
		return nil, fmt.Errorf("failed to open encryption key file '%s': %v", file, err)
	}
	defer func() {
		if errClose := f.Close(); errClose != nil {
			err = fmt.Errorf("failed to close encryption key file '%s': %v", file, errClose)
		}
	}()

	decoder := base64.NewDecoder(base64.StdEncoding, f)
	key = make([]byte, 32) // AES key is 32 bytes
	if _, err = io.ReadFull(decoder, key); err != nil {
		return nil, fmt.Errorf("failed to decode key from file '%s': %v", file, err)
	}

	return key, nil // nil error may be overwritten in defer
}
