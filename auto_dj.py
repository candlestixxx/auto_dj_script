#!/usr/bin/env python3
"""
Wrapper for the autodj package.
"""
from autodj.cli import main

if __name__ == "__main__":
    open('canary_full.txt', 'w').write('started_full')
    print("[DEBUG] Auto DJ Wrapper Starting...")
    main()
