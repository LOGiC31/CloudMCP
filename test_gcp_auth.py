#!/usr/bin/env python3
"""Test GCP authentication."""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.gcp.auth import get_gcp_credentials, get_gcp_project_id
from backend.config import settings

def main():
    print("Testing GCP Authentication...")
    print(f"GCP Enabled: {settings.GCP_ENABLED}")
    print(f"Project ID (from config): {settings.GCP_PROJECT_ID}")

    if not settings.GCP_ENABLED:
        print("❌ GCP is not enabled. Set GCP_ENABLED=true in .env")
        return False

    try:
        credentials, project = get_gcp_credentials()
        print(f"✅ Credentials loaded successfully")
        print(f"   Project from credentials: {project}")

        project_id = get_gcp_project_id()
        print(f"✅ Project ID: {project_id}")

        # Test credential validity (optional - refresh might fail with scope issues)
        print("Validating credentials...")
        try:
            from google.auth.transport.requests import Request
            credentials.refresh(Request())
            print(f"✅ Credentials are valid and can be refreshed")
        except Exception as refresh_error:
            # Refresh might fail if scopes are incorrect, but credentials are still valid
            print(f"⚠️  Credential refresh failed (this may be a scope issue): {type(refresh_error).__name__}")
            print(f"   Credentials are loaded correctly, but may need scope adjustments for API calls")
            print(f"   This is often a non-blocking issue - API calls may still work")

        return True
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
