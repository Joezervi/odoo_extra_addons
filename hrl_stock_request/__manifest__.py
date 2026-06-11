# -*- coding: utf-8 -*-
{
    "name": "Inter-Warehouse Stock Request",
    "author": "Herul Ramdani",
    "website": "https://www.lemacore.com",
    "version": "1.0",
    "category": "Inventory",
    "summary": "Seamlessly request and transfer stock between warehouses with automated two-step internal transfers via transit location",
    "description": """
        Inter-Warehouse Stock Request
        ==============================

        Streamline your multi-warehouse stock replenishment process with a simple, 
        structured request workflow — no manual transfer creation needed

        * 📦 **One-Click Stock Requests** — Create inter-warehouse transfer requests in seconds from a dedicated menu under Inventory > Operations.
        * 🔄 **Automated Two-Step Transfers** — Automatically generates both a Delivery (source → transit) and a Receipt (transit → destination) upon confirmation.
        * 🏭 **Multi-Warehouse Support** — Define source warehouse/location and destination warehouse/location independently per request.
        * 🚦 **Clear Status Workflow** — Track every request through Draft → Confirm → Validate stages with full traceability.
        * 🔗 **Full Traceability** — Each transfer references the originating Stock Request number (e.g. SR/00001) as the source document.
        * 🖨️ **Quick Access to Transfers** — Smart buttons on the request form show linked Delivery and Receipt counts for instant navigation
    """,
    "support": "herulramdani.r16@gmail.com",
    'license': 'OPL-1',
    "depends": ["stock"],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "views/stock_request_views.xml",
    ],
    'installable': True,
    'application': False,
    "images": ['images/thumbnail.png'],
}