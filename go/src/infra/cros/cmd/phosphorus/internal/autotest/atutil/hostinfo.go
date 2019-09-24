package atutil

import (
	"fmt"
	"os"
	"path/filepath"
)

// prepareHostInfo prepares the host info store for the autoserv job
// using the master host info store in the results directory.
func prepareHostInfo(resultsDir string, j AutoservJob) error {
	ja := j.AutoservArgs()
	dstdir := filepath.Join(ja.ResultsDir, hostInfoSubDir)
	if err := os.MkdirAll(dstdir, 0777); err != nil {
		return err
	}
	for _, h := range ja.Hosts {
		f := fmt.Sprintf("%s.store", h)
		src := filepath.Join(resultsDir, hostInfoSubDir, f)
		dst := filepath.Join(dstdir, f)
		if err := linkFile(src, dst); err != nil {
			return err
		}
	}
	return nil
}

// retrieveHostInfo retrieves the host info store for the autoserv job
// back to the master host info store in the results directory.
func retrieveHostInfo(resultsDir string, j AutoservJob) error {
	ja := j.AutoservArgs()
	for _, h := range ja.Hosts {
		f := fmt.Sprintf("%s.store", h)
		src := filepath.Join(ja.ResultsDir, hostInfoSubDir, f)
		dst := filepath.Join(resultsDir, hostInfoSubDir, f)
		if err := linkFile(src, dst); err != nil {
			return err
		}
	}
	return nil
}
