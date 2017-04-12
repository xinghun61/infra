package main

import (
	"context"
	"fmt"
	"path/filepath"
	"sync"
	"time"

	"cloud.google.com/go/storage"

	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/retry"
	"github.com/luci/luci-go/common/tsmon/metric"
	"github.com/luci/luci-go/common/tsmon/types"
)

var (
	filesDeleted = metric.NewCounter("backups/files_deleted",
		"Number of files deleted from GCS",
		&types.MetricMetadata{})
)

// deleteFromGS deletes each filename read from filenamesChan
func delFromGS(ctx context.Context, bucket *storage.BucketHandle, prefix string, filenamesChan <-chan string, workers int, errorChan chan<- error) <-chan struct{} {
	doneChan := make(chan struct{})

	var wg sync.WaitGroup
	wg.Add(workers)

	for i := 0; i < workers; i++ {
		go func() {
			defer wg.Done()

			for filename := range filenamesChan {
				select {
				case _ = <-ctx.Done():
					break
				default:
				}
				objName := prefix + filepath.ToSlash(filename)
				errorChan <- retry.Retry(ctx, retry.TransientOnly(retry.Default), func() error {
					if err := bucket.Object(objName).Delete(ctx); err != nil {
						if err == storage.ErrObjectNotExist {
							return nil
						}
						return fmt.Errorf("Failed to delete object '%s': %v", objName, err)
					}
					filesDeleted.Add(ctx, 1)
					return nil
				}, func(err error, d time.Duration) {
					logging.Warningf(ctx, "Transient error on GS delete. Retrying in %.1fs ...: %v", d.Seconds(), err)
				})
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
