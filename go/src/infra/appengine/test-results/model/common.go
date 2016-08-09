package model

import (
	"bytes"
	"math"
	"strconv"
)

func round(f float64) int {
	if math.Abs(f) < 0.5 {
		return 0
	}
	return int(f + math.Copysign(0.5, f))
}

// TestNode is a node in a Tests tree.
type TestNode interface {
	// Children returns a map of a TestNode's children.
	Children() map[string]TestNode

	testnode()
}

// number is an integer that supports JSON unmarshaling from a string
// and marshaling back to a string.
type number int

func (n *number) UnmarshalJSON(data []byte) error {
	data = bytes.Trim(data, `"`)
	num, err := strconv.Atoi(string(data))
	if err != nil {
		return err
	}
	*n = number(num)
	return nil
}

func (n *number) MarshalJSON() ([]byte, error) {
	return []byte(strconv.Itoa(int(*n))), nil
}
