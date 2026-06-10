# Copyright 2018-2026 Sodexis
# License OPL-1 (See LICENSE file for full copyright and licensing details).

{
    "name": "Restrict Delete for MO",
    "summary": """
        This module is used to restrict the delete option for  Manufacturing Order""",
    "version": "19.0.1.0.0",
    "category": "Manufacturing",
    "website": "https://sodexis.com/",
    "author": "Sodexis",
    "license": "OPL-1",
    "installable": True,
    "application": False,
    "images": ["images/main_screenshot.jpg"],
    "live_test_url": "https://sodexis.com/odoo-apps-store-demo",
    "depends": [
        "mrp",
    ],
    "data": [
        "security/security.xml",
    ],
}
