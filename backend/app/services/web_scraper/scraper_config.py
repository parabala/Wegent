# SPDX-FileCopyrightText: 2025 Weibo, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""
Web scraper service constants and site-specific configurations.
"""

import json
import os

# ========== Web Scraper Site-Specific Configuration ==========
# Configuration for specific sites that require special handling
# due to anti-bot detection, dynamic content loading, or navigation patterns
# Loaded from environment variable WEB_SCRAPER_SITE_CONFIG


def _load_site_config():
    """Load site configuration from environment variable."""
    config_str = os.environ.get("WEB_SCRAPER_SITE_CONFIG", "{}")
    try:
        return json.loads(config_str)
    except json.JSONDecodeError:
        return {}


WEB_SCRAPER_SITE_CONFIG = _load_site_config()
