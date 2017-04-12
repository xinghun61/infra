// +build windows

package main

import (
	"context"

	"github.com/luci/luci-go/common/logging"
	"golang.org/x/sys/windows"
)

func getFs(ctx context.Context, path string) (fs uint64, err error) {
	if len(path) == 0 {
		return 0, windows.ERROR_FILE_NOT_FOUND
	}
	pathp, err := windows.UTF16PtrFromString(path)
	if err != nil {
		return 0, err
	}

	// Use windows.CreateFile directly rather than os.Open, because the flag
	// FILE_FLAG_BACKUP_SEMANTICS needs to be used to get a handle to a directory,
	// which isn't implemented in existing Open/OpenFile functions in os/syscall/windows packages
	handle, err := windows.CreateFile(
		pathp,
		windows.GENERIC_READ,    // dwDesiredAccess
		windows.FILE_SHARE_READ, // dwShareMode
		nil, // lpSecurityAttributes
		windows.OPEN_EXISTING,                                            // dwCreationDisposition
		windows.FILE_ATTRIBUTE_NORMAL|windows.FILE_FLAG_BACKUP_SEMANTICS, // dwFlagsAndAttributes
		0, // hTemplateFile
	)
	if err != nil {
		logging.Errorf(ctx, "Failed to open file '%s': %v", path, err)
		return 0, err
	}
	defer func() {
		if errClose := windows.CloseHandle(handle); errClose != nil {
			if err == nil {
				err = errClose
			}
			logging.Errorf(ctx, "Failed to close handle")
		}
	}()

	var info windows.ByHandleFileInformation
	if err := windows.GetFileInformationByHandle(handle, &info); err != nil {
		logging.Errorf(ctx, "Failed to get FileInformation: %v", err)
		return 0, err
	}
	return uint64(info.VolumeSerialNumber), nil
}
