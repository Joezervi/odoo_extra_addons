{
    "name": "Sales Deposit Request",
    "version": "19.0.1.0.0",
    "category": "Sales",
    "depends": [
        "sale_management",
        "account",
        "mail",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",

        "data/sequence.xml",
        "data/deposit_product.xml",

        "views/sale_deposit_request_views.xml",
        # "views/sale_deposit_request_menu.xml",
        "views/sale_deposit_wizard_views.xml",
        "views/account_invoice_view.xml",
    ],
    "application": True,
    "license": "LGPL-3",
}