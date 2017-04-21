// +build darwin linux

package main

import (
	"context"
	"fmt"
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

	realStat, ok := stat.Sys().(*syscall.Stat_t)
	if !ok {
		return 0, fmt.Errorf("Failed to convert stat.Sys() to syscall.Stat_t for file '%s'", filename)
	}
	if realStat == nil {
		logging.Warningf(ctx, "Unable to get OS-level stat data for file '%s'. Returning 0 for filesystem id.")
		return 0, nil
	}

	return uint64(realStat.Dev), nil
}
