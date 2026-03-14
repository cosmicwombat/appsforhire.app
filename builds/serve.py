#!/usr/bin/env python3
"""
AppsForHire — Local Test Server

Usage:
    python3 serve.py                  # lists available builds
    python3 serve.py theghostkitchen  # serves that build on port 8000
    python3 serve.py theghostkitchen 3000  # custom port

Opens in your browser automatically. Ctrl+C to stop.
"""

import http.server
import os
import sys
import webbrowser

def get_builds():
    """Find all build folders (ones that contain an index.html)."""
    here = os.path.dirname(os.path.abspath(__file__))
    builds = []
    for name in sorted(os.listdir(here)):
        path = os.path.join(here, name)
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, "index.html")):
            builds.append(name)
    return builds

def main():
    builds = get_builds()

    # No argument — show available builds
    if len(sys.argv) < 2:
        print("\n  Available builds:\n")
        for i, b in enumerate(builds, 1):
            print(f"    {i}. {b}")
        print(f"\n  Usage:  python3 serve.py <build-name> [port]")
        print(f"  Example: python3 serve.py {builds[0] if builds else 'myapp'}\n")
        sys.exit(0)

    slug = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000

    # Resolve the build directory
    here = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.join(here, slug)

    if not os.path.isdir(build_dir):
        print(f"\n  Error: no build folder found at {build_dir}")
        print(f"  Available: {', '.join(builds)}\n")
        sys.exit(1)

    if not os.path.isfile(os.path.join(build_dir, "index.html")):
        print(f"\n  Error: {slug}/ has no index.html\n")
        sys.exit(1)

    os.chdir(build_dir)

    handler = http.server.SimpleHTTPRequestHandler
    # Suppress noisy request logs — show just errors
    handler.log_message = lambda self, fmt, *args: None

    server = http.server.HTTPServer(("0.0.0.0", port), handler)

    url = f"http://localhost:{port}"
    print(f"\n  Serving: {slug}")
    print(f"  App:     {url}")
    print(f"  Portal:  {url}/portal/")
    print(f"  Ctrl+C to stop\n")

    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.\n")
        server.server_close()

if __name__ == "__main__":
    main()
