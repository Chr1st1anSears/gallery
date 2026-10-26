"""Grant or revoke Gallery editor access for a user.

Editors can add, edit and delete photos. Editor access is stored as a Firebase
Auth custom claim (`editor: true`), which is checked by the Cloud Functions,
the Cloud Storage rules and the web UI.

The user must have signed in to the app at least once (so their account
exists) before you can grant access.

Usage (uses Application Default Credentials; run
`gcloud auth application-default login` first):

    python scripts/set_editor.py --project YOUR_PROJECT_ID you@example.com
    python scripts/set_editor.py --project YOUR_PROJECT_ID --revoke someone@example.com
    python scripts/set_editor.py --project YOUR_PROJECT_ID --list

After a change, the user must sign out and back in (or wait up to an hour) for
their ID token to pick up the new claim.
"""

import argparse
import sys

import firebase_admin
from firebase_admin import auth


def set_editor(email: str, enabled: bool) -> None:
    user = auth.get_user_by_email(email)
    claims = dict(user.custom_claims or {})
    if enabled:
        claims["editor"] = True
    else:
        claims.pop("editor", None)
    auth.set_custom_user_claims(user.uid, claims or None)
    print(f"{'Granted' if enabled else 'Revoked'} editor access for {email} (uid {user.uid}).")


def list_editors() -> None:
    found = False
    for user in auth.list_users().iterate_all():
        if (user.custom_claims or {}).get("editor") is True:
            print(f"{user.email}\t{user.uid}")
            found = True
    if not found:
        print("No editors found.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", required=True, help="Firebase / GCP project ID.")
    parser.add_argument("--revoke", action="store_true", help="Revoke instead of grant.")
    parser.add_argument("--list", action="store_true", help="List current editors.")
    parser.add_argument("emails", nargs="*", help="Email address(es) of existing users.")
    args = parser.parse_args()

    firebase_admin.initialize_app(options={"projectId": args.project})

    if args.list:
        list_editors()
        return 0
    if not args.emails:
        parser.error("provide at least one email, or --list")

    status = 0
    for email in args.emails:
        try:
            set_editor(email, enabled=not args.revoke)
        except auth.UserNotFoundError:
            print(f"No user with email {email}. Have them sign in to the app once first.", file=sys.stderr)
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
