#!/usr/bin/env python3
"""
play_store_tracks.py — Read-only Google Play track inspection for CI.

Opens a temporary Play Console edit (committing nothing — the edit is always
abandoned at the end), then either lists the available track IDs or reports
each track's release status, rollout fraction, and versionCodes. Used by
.github/workflows/android-publish.yml to (a) discover trackIds for the
ANDROID_AUTO_TRACK / ANDROID_EXTRA_TRACKS variables and (b) give post-upload
visibility into what actually landed on each track.

Note: the `status` reported here is the *target* state set by the upload
(completed / draft / inProgress / halted) and the rollout fraction — NOT
Google's review state. The Play Developer API exposes no "in review" field,
so a release shown as `completed` / 100% may still be held in review; the Play
Console UI is the source of truth for review status.

Usage:
    python3 android/scripts/play_store_tracks.py list      # print track IDs
    python3 android/scripts/play_store_tracks.py status     # per-track releases

Environment:
    GOOGLE_PLAY_JSON_KEY_FILE  service-account JSON path
                               (default: /tmp/google-play-key.json)
    PLAY_PACKAGE_NAME          app package name (default: org.voxquieta)
"""
import json
import os
import sys

from google.oauth2 import service_account
from googleapiclient.discovery import build

PACKAGE = os.environ.get("PLAY_PACKAGE_NAME", "org.voxquieta")
KEY_FILE = os.environ.get("GOOGLE_PLAY_JSON_KEY_FILE", "/tmp/google-play-key.json")
SCOPES = ["https://www.googleapis.com/auth/androidpublisher"]


def _service():
    with open(KEY_FILE) as f:
        creds_data = json.load(f)
    creds = service_account.Credentials.from_service_account_info(creds_data, scopes=SCOPES)
    return build("androidpublisher", "v3", credentials=creds)


def list_tracks(tracks):
    print("Available Play Store tracks (use trackId value in the track dropdown):")
    for t in sorted(tracks, key=lambda x: x["track"]):
        print(f'  trackId: "{t["track"]}"')


def report_status(tracks):
    print("Play Store track status (post-upload, read-only):")
    print("=" * 64)
    for t in sorted(tracks, key=lambda x: x["track"]):
        releases = t.get("releases", [])
        print(f'\ntrack: "{t["track"]}"')
        if not releases:
            print("  (no releases)")
            continue
        for r in releases:
            # status: completed | inProgress | draft | halted (target state,
            # not review state — see module docstring).
            status = r.get("status", "?")
            frac = r.get("userFraction")
            if frac is not None:
                rollout = f"{float(frac) * 100:.0f}%"
            elif status == "completed":
                rollout = "100%"
            else:
                rollout = "n/a"
            codes = ", ".join(str(c) for c in r.get("versionCodes", [])) or "-"
            print(f"  - versionCodes: [{codes}]")
            print(f"    name:         {r.get('name', '')}")
            print(f"    status:       {status}")
            print(f"    userFraction: {rollout}")
            ctry = r.get("countryTargeting")
            if ctry:
                print(f"    countryTargeting: {json.dumps(ctry)}")
    print("=" * 64)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "status"
    if mode not in ("list", "status"):
        print(f"usage: {sys.argv[0]} [list|status]", file=sys.stderr)
        return 2

    service = _service()
    # A temporary edit is required by the API to read track state.
    edit = service.edits().insert(packageName=PACKAGE).execute()
    edit_id = edit["id"]
    try:
        tracks = (
            service.edits()
            .tracks()
            .list(packageName=PACKAGE, editId=edit_id)
            .execute()
            .get("tracks", [])
        )
        if mode == "list":
            list_tracks(tracks)
        else:
            report_status(tracks)
    finally:
        # Abandon the edit — no changes committed to Play Console.
        service.edits().delete(packageName=PACKAGE, editId=edit_id).execute()
        print("Edit abandoned — no changes committed.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
