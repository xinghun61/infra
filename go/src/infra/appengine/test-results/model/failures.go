package model

var failureTypes = map[string]string{
	"A": "AUDIO",
	"C": "CRASH",
	"Q": "FAIL",

	// This is only output by gtests.
	// TODO(nishanths): Address above comment copied from .py file.
	"L": "FLAKY",
	"I": "IMAGE",
	"Z": "IMAGE+TEXT",
	"K": "LEAK",
	"O": "MISSING",
	"N": "NO DATA",
	"Y": "NOTRUN",
	"P": "PASS",
	"X": "SKIP",
	"S": "SLOW",
	"F": "TEXT",
	"T": "TIMEOUT",
	"U": "UNKNOWN",
	"V": "VERYFLAKY",
}
