// Code generated by "stringer -type inventoryTypes"; DO NOT EDIT.

package cmd

import "strconv"

const _inventoryTypes_name = "inventoryTypeLabinventoryTypeInfra"

var _inventoryTypes_index = [...]uint8{0, 16, 34}

func (i inventoryTypes) String() string {
	i -= 1
	if i >= inventoryTypes(len(_inventoryTypes_index)-1) {
		return "inventoryTypes(" + strconv.FormatInt(int64(i+1), 10) + ")"
	}
	return _inventoryTypes_name[_inventoryTypes_index[i]:_inventoryTypes_index[i+1]]
}