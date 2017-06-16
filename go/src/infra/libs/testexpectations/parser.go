// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package testexpectations

// Package testexpectations provides a parser for layout test expectation
// files.

import (
	"bufio"
	"bytes"
	"fmt"
	"io"
	"strings"
)

// ExpectationStatement represents a statement (one line) from a layout test
// expectation file.
type ExpectationStatement struct {
	// LineNumber from the original input file.
	LineNumber int
	// Comment, if any.
	Comment string
	// Bugs associated with the test expectation.
	Bugs []string
	// Modifiers (optional) for the test expectation/
	Modifiers []string
	// TestName identifies the test file or test directory.
	TestName string
	// Expectations is a list of expected test results.
	Expectations []string
	// Original line content.
	Original string
	// Dirty indicates that fields have changed since Original was parsed.
	Dirty bool
}

func (e *ExpectationStatement) String() string {
	if !e.Dirty {
		return e.Original
	}

	if e.TestName == "" {
		return e.Comment
	}

	ret := strings.Join(e.Bugs, " ")

	if len(e.Modifiers) > 0 {
		ret = fmt.Sprintf("%s [ %s ]", ret, strings.Join(e.Modifiers, " "))
	}

	if e.Comment != "" {
		return fmt.Sprintf("%s %s [ %s ] %s", ret, e.TestName, strings.Join(e.Expectations, " "), e.Comment)
	}

	ret = fmt.Sprintf("%s %s", ret, e.TestName)

	if len(e.Expectations) > 0 {
		ret = fmt.Sprintf("%s [ %s ]", ret, strings.Join(e.Expectations, " "))
	}
	return strings.Trim(ret, " ")
}

type token int

// Constants for internal token types.
const (
	tokIllegal token = iota
	tokEOF
	tokWS
	tokIDENT
	tokLB
	tokRB
	tokHASH
)

func isWhitespace(ch rune) bool {
	return ch == ' ' || ch == '\t' || ch == '\n'
}

func isIdentStart(ch rune) bool {
	return ch != ' ' && ch != '[' && ch != ']' && ch != '#'
}

var eof = rune(0)

type scanner struct {
	r *bufio.Reader
}

func newScanner(r io.Reader) *scanner {
	return &scanner{r: bufio.NewReader(r)}
}

func (s *scanner) read() rune {
	ch, _, err := s.r.ReadRune()
	if err != nil {
		return eof
	}
	return ch
}

func (s *scanner) unread() { _ = s.r.UnreadRune() }

func (s *scanner) scan() (tok token, lit string) {
	ch := s.read()

	if isWhitespace(ch) {
		s.unread()
		return s.scanWhitespace()
	} else if isIdentStart(ch) {
		s.unread()
		return s.scanIdent()
	}

	switch ch {
	case eof:
		return tokEOF, ""
	case '#':
		return tokHASH, string(ch)
	case '[':
		return tokLB, string(ch)
	case ']':
		return tokRB, string(ch)
	}

	return tokIllegal, string(ch)
}

func (s *scanner) scanWhitespace() (tok token, lit string) {
	var buf bytes.Buffer
	buf.WriteRune(s.read())

	for {
		if ch := s.read(); ch == eof {
			break
		} else if !isWhitespace(ch) {
			s.unread()
			break
		} else {
			buf.WriteRune(ch)
		}
	}

	return tokWS, buf.String()
}

func (s *scanner) scanIdent() (tok token, lit string) {
	var buf bytes.Buffer
	buf.WriteRune(s.read())

	for {
		if ch := s.read(); ch == eof {
			break
		} else if ch == '[' || ch == ']' || ch == '#' || isWhitespace(ch) {
			s.unread()
			break
		} else {
			buf.WriteRune(ch)
		}
	}
	return tokIDENT, buf.String()
}

// Parser parses layout test expectation files.
type Parser struct {
	s   *scanner
	buf struct {
		tok token
		lit string
		n   int
	}
	original string
}

// NewParser returns a new instance of Parser for io.Reader input.
func NewParser(r io.Reader) *Parser {
	return &Parser{s: newScanner(r)}
}

// NewStringParser returns a new instance of Parser for string input.
func NewStringParser(str string) *Parser {
	return &Parser{s: newScanner(bytes.NewBufferString(str)), original: str}
}

func (p *Parser) scan() (tok token, lit string) {
	if p.buf.n != 0 {
		p.buf.n = 0
		return p.buf.tok, p.buf.lit
	}

	tok, lit = p.s.scan()

	p.buf.tok, p.buf.lit = tok, lit

	return
}

func (p *Parser) unscan() { p.buf.n = 1 }

func (p *Parser) scanIgnoreWhitespace() (tok token, lit string) {
	tok, lit = p.scan()
	for tok == tokWS {
		tok, lit = p.scan()
	}
	return
}

func isBug(s string) bool {
	return strings.HasPrefix(s, "crbug.com/") || strings.HasPrefix(s, "Bug(") || strings.HasPrefix(s, "webkit.org/b/")
}

// Parse parses a *line* of input to produce an ExpectationStatement, or error.
func (p *Parser) Parse() (*ExpectationStatement, error) {
	stmt := &ExpectationStatement{Original: p.original}
	tok, lit := p.scanIgnoreWhitespace()

	// Exit early for a blank line.
	if lit == string(eof) {
		return stmt, nil
	}

	if tok != tokHASH && tok != tokLB && tok != tokIDENT {
		return nil, fmt.Errorf("expected tokHASH (comment), tokLB (modifier), or tokIDENT (start of expectation rule) but found %q", lit)
	}

	// Check for optional: tokHASH comment, return early with the entire line.
	if tok == tokHASH {
		stmt.Comment = lit
		ch := p.s.read()
		for ; ch != eof; ch = p.s.read() {
			stmt.Comment = stmt.Comment + string(ch)
		}
		return stmt, nil
	}

	// Check for modifiers at start of statement.
	if tok == tokLB {
		for tok != tokRB {
			tok, lit = p.scanIgnoreWhitespace()
			if tok == tokIDENT {
				stmt.Modifiers = append(stmt.Modifiers, lit)
			} else if tok != tokRB {
				return nil, fmt.Errorf("expected tokIDENT or tokRB for modifiers, but found %q", lit)
			}
		}
	}

	// Check for tokIDENT bugs.
	if tok == tokIDENT {
		if isBug(lit) {
			for {
				stmt.Bugs = append(stmt.Bugs, lit)
				tok, lit = p.scanIgnoreWhitespace()
				if !isBug(lit) {
					p.unscan()
					break
				}
			}
		} else {
			// Line starts with the test name, no bugs.
			stmt.TestName = lit
		}
	}

	tok, lit = p.scanIgnoreWhitespace()

	if tok != tokLB && tok != tokIDENT && tok != tokWS {
		return nil, fmt.Errorf("expected tokLB, tokIDENT or tokWS but found %q", lit)
	}

	// Check for optional: tokLB modifiers tokRB.
	if tok == tokLB {
		for {
			tok, lit = p.scanIgnoreWhitespace()
			if tok == tokIDENT {
				if stmt.TestName == "" {
					stmt.Modifiers = append(stmt.Modifiers, lit)
				} else {
					stmt.Expectations = append(stmt.Expectations, lit)
				}
			} else if tok == tokRB {
				// Scan past the tokRB so testname can parse.
				tok, lit = p.scanIgnoreWhitespace()
				break
			} else {
				return nil, fmt.Errorf("expected tokIDENT or tokRB for modifiers, but found %q", lit)
			}
		}
	}

	// Check for tokIDENT testname.
	if tok == tokIDENT && stmt.TestName == "" {
		stmt.TestName = lit
	}

	tok, lit = p.scanIgnoreWhitespace()
	if tok != tokLB && tok != tokIDENT && tok != tokWS {
		return nil, fmt.Errorf("expected tokLB, tokIDENT or tokWS but found %q", lit)
	}

	// check for tokLB expectations tokRB.
	if tok == tokLB {
		for {
			tok, lit = p.scanIgnoreWhitespace()
			if tok == tokIDENT {
				stmt.Expectations = append(stmt.Expectations, lit)
			} else if tok == tokRB {
				break
			} else {
				return nil, fmt.Errorf("expected tokIDENT or tokRB for expectations, but found %q", lit)
			}
		}
	} else if lit != string(eof) {
		return nil, fmt.Errorf("expected tokLB or tokIDENT for expectations, but found %q", lit)
	}

	tok, lit = p.scanIgnoreWhitespace()
	// Check for optional: tokHASH comment at the end of a line.
	if tok == tokHASH {
		stmt.Comment = lit
		ch := p.s.read()
		for ; ch != eof; ch = p.s.read() {
			stmt.Comment = stmt.Comment + string(ch)
		}
	}

	return stmt, nil
}
