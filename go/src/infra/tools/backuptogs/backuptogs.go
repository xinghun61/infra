package main

import (
	"compress/gzip"
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sync"
	"time"

	"cloud.google.com/go/storage"

	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/retry"
	"github.com/luci/luci-go/common/tsmon/metric"
	"github.com/luci/luci-go/common/tsmon/types"
)

var (
	bytesBackedUp = metric.NewCounter("backups/bytes_backed_up",
		"Cumulative size of files backed up",
		&types.MetricMetadata{Units: types.Bytes})
	filesBackedUp = metric.NewCounter("backups/files_backed_up",
		"Number of files actually backed up",
		&types.MetricMetadata{})
	bytesStored = metric.NewCounter("backups/bytes_stored",
		"Cumulative size of objects stored in GCS",
		&types.MetricMetadata{Units: types.Bytes})
)

// backupToGS backs up each filename read from filenameChan to GCS
// it spawns worker goroutines and returns a channel that will be
// closed when all workers have finished.
func backupToGS(
	ctx context.Context,
	filenameChan <-chan string,
	bucket *storage.BucketHandle,
	prefix string,
	key []byte,
	workers int,
	errorChan chan<- error) <-chan struct{} {

	doneChan := make(chan struct{})
	var wg sync.WaitGroup
	wg.Add(workers)

	for i := 0; i < workers; i++ {
		go func() {
			defer wg.Done()

			for filename := range filenameChan {
				select {
				case _ = <-ctx.Done():
					break
				default:
				}

				objName := prefix + filepath.ToSlash(filename)
				written, err := writeToGS(ctx, filename, bucket, objName, key)
				if err != nil {
					if os.IsNotExist(err) { // Non-existent files are tolerable
						logging.Warningf(ctx, "File intended for backup was not found: %s", filename)
						continue
					}
					errorChan <- fmt.Errorf("Failed to copy file '%s' to GCS: %v", filename, err)
					continue
				}

				filesBackedUp.Add(ctx, 1)
				bytesBackedUp.Add(ctx, written)
			}
		}()
	}

	go func() {
		wg.Wait()
		logging.Debugf(ctx, "WaitGroup is finished")
		doneChan <- struct{}{}
	}()

	return doneChan
}

func writeToGS(ctx context.Context, filename string, bucket *storage.BucketHandle, objname string, key []byte) (int64, error) {
	obj := bucket.Object(objname)

	if key != nil {
		obj = obj.Key(key)
	}

	// TODO set metadata on obj

	var written int64
	err := retry.Retry(ctx, retry.TransientOnly(retry.Default), func() (err error) {
		gsWriter := obj.NewWriter(ctx)
		defer func() {
			if errGs := gsWriter.Close(); errGs != nil {
				err = errors.WrapTransient(fmt.Errorf("Failed to close gcsWriter: %v", errGs))
				return
			}
			bytesStored.Add(ctx, gsWriter.Attrs().Size)
		}()

		zipWriter := gzip.NewWriter(gsWriter)
		defer func() {
			if errZip := zipWriter.Close(); errZip != nil {
				err = fmt.Errorf("Failed to close gzipWriter: %v", errZip)
			}
		}()

		f, err := os.Open(filename)
		if err != nil {
			logging.Warningf(ctx, "Failed to open file '%s': %v", filename, err)
			return err
		}
		defer func() {
			if errClose := f.Close(); errClose != nil {
				err = errClose
			}
		}()

		if written, err = io.Copy(zipWriter, f); err != nil {
			// FIXME determine if error really is transient
			return errors.WrapTransient(fmt.Errorf("Failed to backup file '%s': %v", filename, err))
		}

		return nil
	}, func(err error, d time.Duration) {
		logging.Warningf(ctx, "Transient error on GS write. Retrying in %.1fs ...: %v", d.Seconds(), err)
	})

	return written, err
}
