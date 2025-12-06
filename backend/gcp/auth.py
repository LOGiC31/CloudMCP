"""GCP authentication utilities."""
import os
from typing import Optional
from google.auth import default, load_credentials_from_file
from google.auth.exceptions import DefaultCredentialsError
from google.oauth2 import service_account
from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def get_gcp_credentials():
    """
    Get GCP credentials for API authentication.
    
    Priority:
    1. Service account key file (if GCP_SERVICE_ACCOUNT_KEY_PATH is set)
    2. Application Default Credentials (ADC)
    3. Environment variable GOOGLE_APPLICATION_CREDENTIALS
    
    Returns:
        google.auth.credentials.Credentials: GCP credentials
        
    Raises:
        DefaultCredentialsError: If no credentials can be found
    """
    try:
        # Method 1: Service account key file from config
        if settings.GCP_SERVICE_ACCOUNT_KEY_PATH and os.path.exists(settings.GCP_SERVICE_ACCOUNT_KEY_PATH):
            logger.info(f"Loading GCP credentials from key file: {settings.GCP_SERVICE_ACCOUNT_KEY_PATH}")
            try:
                # Try loading with explicit service account credentials
                from google.oauth2 import service_account
                credentials = service_account.Credentials.from_service_account_file(
                    settings.GCP_SERVICE_ACCOUNT_KEY_PATH,
                    scopes=[
                        'https://www.googleapis.com/auth/cloud-platform',
                        'https://www.googleapis.com/auth/compute',
                        'https://www.googleapis.com/auth/sqlservice.admin',
                        'https://www.googleapis.com/auth/cloud-redis',
                        'https://www.googleapis.com/auth/monitoring.read',
                    ]
                )
                # Get project from credentials file
                import json
                with open(settings.GCP_SERVICE_ACCOUNT_KEY_PATH, 'r') as f:
                    key_data = json.load(f)
                    project = key_data.get('project_id')
                return credentials, project
            except Exception as e:
                logger.warning(f"Failed to load credentials using service_account.Credentials: {e}, trying load_credentials_from_file")
                # Fallback to original method
                credentials, project = load_credentials_from_file(
                    settings.GCP_SERVICE_ACCOUNT_KEY_PATH,
                    scopes=[
                        'https://www.googleapis.com/auth/cloud-platform',
                        'https://www.googleapis.com/auth/compute',
                        'https://www.googleapis.com/auth/sqlservice.admin',
                        'https://www.googleapis.com/auth/cloud-redis',
                        'https://www.googleapis.com/auth/monitoring.read',
                    ]
                )
                return credentials, project
        
        # Method 2: Environment variable
        env_key_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if env_key_path and os.path.exists(env_key_path):
            logger.info(f"Loading GCP credentials from GOOGLE_APPLICATION_CREDENTIALS: {env_key_path}")
            credentials, project = load_credentials_from_file(
                env_key_path,
                scopes=[
                    'https://www.googleapis.com/auth/cloud-platform',
                    'https://www.googleapis.com/auth/compute',
                    'https://www.googleapis.com/auth/sqlservice.admin',
                    'https://www.googleapis.com/auth/cloud-redis',
                    'https://www.googleapis.com/auth/monitoring.read',
                ]
            )
            return credentials, project
        
        # Method 3: Application Default Credentials (ADC)
        logger.info("Using Application Default Credentials (ADC)")
        credentials, project = default(scopes=[
            'https://www.googleapis.com/auth/cloud-platform',
            'https://www.googleapis.com/auth/compute',
            'https://www.googleapis.com/auth/sqlservice.admin',
            'https://www.googleapis.com/auth/cloud-redis',
            'https://www.googleapis.com/auth/monitoring.read',
        ])
        return credentials, project
        
    except DefaultCredentialsError as e:
        logger.error(f"Failed to get GCP credentials: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting GCP credentials: {e}", exc_info=True)
        raise


def get_gcp_project_id() -> str:
    """
    Get GCP project ID from config or credentials.
    
    Returns:
        str: GCP project ID
        
    Raises:
        ValueError: If project ID cannot be determined
    """
    if settings.GCP_PROJECT_ID:
        return settings.GCP_PROJECT_ID
    
    try:
        _, project = get_gcp_credentials()
        if project:
            return project
    except Exception as e:
        logger.debug(f"Could not get project from credentials: {e}")
    
    # Try environment variable
    project_id = os.environ.get('GOOGLE_CLOUD_PROJECT') or os.environ.get('GCP_PROJECT_ID')
    if project_id:
        return project_id
    
    raise ValueError(
        "GCP project ID not found. Set GCP_PROJECT_ID in config or GOOGLE_CLOUD_PROJECT environment variable."
    )

