#!/usr/bin/env python3
import re
import cleanup_buildings as c

# The v1 regexes used \s* at the beginning of line. In Python that can consume
# newlines, so replacement spans could start on the previous blank line and make
# comments visually attach to STATE lines. Restrict leading indentation to spaces/tabs.
c.STATE_RE = re.compile(r'(?m)^[ \t]*s:(STATE_[A-Za-z0-9_]+)[ \t]*=[ \t]*\{')
c.REGION_RE = re.compile(r'(?m)^[ \t]*region_state:([A-Za-z0-9_]+)[ \t]*=[ \t]*\{')
c.BUILD_RE = re.compile(r'(?m)^[ \t]*create_building[ \t]*=[ \t]*\{')
c.OWN_RE = re.compile(r'(?m)^[ \t]*add_ownership[ \t]*=[ \t]*\{')
c.OWN_ENTRY_RE = re.compile(r'(?m)^[ \t]*(country|building)[ \t]*=[ \t]*\{')

if __name__ == '__main__':
    c.main()
