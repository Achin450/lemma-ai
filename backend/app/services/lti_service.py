"""
LTI 1.3 Service

Handles LTI 1.3 Advantage integrations for LMS platforms like Canvas, Moodle, and Blackboard.
Provides OIDC login flows, deep linking, and assignment grade passback.
"""
import logging
from typing import Optional
from pylti1p3.tool_config import ToolConfDict
from pylti1p3.registration import Registration
from app.config import settings

logger = logging.getLogger(__name__)

class LTIService:
    """Manages LTI 1.3 integrations for institutional LMS plugins."""
    
    _tool_conf = None

    @classmethod
    def get_tool_conf(cls) -> ToolConfDict:
        """
        Lazily initialize and return the PyLTI1p3 ToolConfDict.
        In a full production environment, this would load configurations from the `lti_platforms` table.
        """
        if cls._tool_conf is not None:
            return cls._tool_conf
            
        # Hardcoded default config for demonstration purposes
        settings_dict = {
            "https://canvas.instructure.com": {
                "client_id": "lemma_canvas_client_123",
                "auth_login_url": "https://canvas.instructure.com/api/lti/authorize_redirect",
                "auth_token_url": "https://canvas.instructure.com/login/oauth2/token",
                "auth_audience": None,
                "key_set_url": "https://canvas.instructure.com/api/lti/security/jwks",
                "key_set": None,
                "private_key_file": None,  # Requires RSA private key in prod
                "public_key_file": None,
                "deployment_ids": ["deployment_1"]
            }
        }
        
        try:
            cls._tool_conf = ToolConfDict(settings_dict)
            logger.info("LTI Tool Configuration initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize LTI Tool Configuration: {e}")
            cls._tool_conf = ToolConfDict({})
            
        return cls._tool_conf

    @classmethod
    def generate_jwks(cls) -> dict:
        """
        Generates the JSON Web Key Set (JWKS) required for LMS platforms 
        to verify messages sent from this tool.
        """
        try:
            tool_conf = cls.get_tool_conf()
            return tool_conf.get_jwks()
        except Exception as e:
            logger.error(f"Failed to generate JWKS: {e}")
            return {"keys": []}
            
    @classmethod
    def get_launch_data(cls, request_data: dict) -> dict:
        """
        Mock extraction of LTI launch data from an OIDC payload.
        """
        logger.info(f"Processing LTI launch data: {request_data.keys()}")
        return {
            "user_id": "lti_user_123",
            "roles": ["http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor"],
            "context_id": "course_101",
            "context_title": "Introduction to Academic Writing",
            "resource_link_id": "assignment_1"
        }
