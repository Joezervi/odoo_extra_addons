{
    "name": "Manufacture Order Edit Restriction",
    "version": "18.0",
    "category": "Manufacturing",
    "summary": "This module allows you to restrict users from editing manufacturing orders. It helps prevent unauthorized changes in manufacturing order details, production records, and related manufacturing information. This is useful for maintaining accurate production data, avoiding accidental modifications, and controlling manufacturing order edit access based on user permissions. Keywords: manufacturing order edit restriction, manufacture order edit restriction, restrict manufacturing order edit, prevent manufacturing order changes, manufacturing order lock, production order edit restriction, prevent production order modification, MO edit restriction, MO edit prevention, restrict MO editing, block MO editing, manufacturing order access control, production order access control, MO user permission, manufacturing order user permission, restrict manufacturing modification, prevent accidental MO changes, production record protection, manufacturing data protection, locked manufacturing order, no edit manufacturing order, manufacturing order security.\n",
    "description": "The Manufacture Order Edit Restriction module enhances control and data integrity within Odoo manufacturing workflow by preventing unauthorized modifications to manufacturing orders. It allows administrators or designated managers to restrict specific users from editing manufacturing records, ensuring that once critical production data is set, it remains consistent and protected.",
    "author": "INKERP",
    "website": "http://www.inkerp.com",
    "depends": [
        "mrp"
    ],
    "data": [
        "security/group.xml"
    ],
    "images": [
        "static/description/banner.gif"
    ],
    "license": "OPL-1",
    "installable": True,
    "application": True,
    "auto_install": False,
    "price": "0.0",
    "currency": "EUR"
}