// Code generated by "stringer -type=AdminTaskType"; DO NOT EDIT.

package atutil

import "fmt"

const _AdminTaskType_name = "NoTaskVerifyCleanupResetRepair"

var _AdminTaskType_index = [...]uint8{0, 6, 12, 19, 24, 30}

func (i AdminTaskType) String() string {
	if i < 0 || i >= AdminTaskType(len(_AdminTaskType_index)-1) {
		return fmt.Sprintf("AdminTaskType(%d)", i)
	}
	return _AdminTaskType_name[_AdminTaskType_index[i]:_AdminTaskType_index[i+1]]
}
