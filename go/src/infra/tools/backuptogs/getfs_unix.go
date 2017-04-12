// +build darwin linux

package main

import (
	"context"
	"os"
	"syscall"

	"github.com/luci/luci-go/common/logging"
)

func getFs(ctx context.Context, filename string) (uint64, error) {
	stat, err := os.Lstat(filename)
	if err != nil {
		logging.Errorf(ctx, "Failed to stat file '%s': %v", filename, err)
		return 0, err
	}

	realStat, ok := stat.Sys().(syscall.Stat_t)
	if !ok {
		logging.Errorf(ctx, "Failed to convert stat.Sys() to syscall.Stat_t for file '%s': %v", filename, err)
		return 0, err
	}

	return uint64(realStat.Dev), nil
}
