# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.
{
	"name":"Lots & Serial Numbers Expiry",
	"version":"19.0.0.0",
	"category":"Warehouse",
	"summary":"Serial Number Expiry Warning Restrict Expired Lot Number Product Lot Numbers Expiration Lots and Serial Numbers Validation Generate Warning of Expired Lot Number Access Control Batch Number Expiration Warning Serial Number Product Serial Expiry Lot Expiry",
	"description":"""
		
		Lots & Serial Numbers Expiry Odoo App helps users to generate warning as per the expiration of lot and serial in the product, along with that it will also restrict the expired lot. When lot is entered of product, if the lot is expired then it will generate an error message.
	
	""",
	"author": "BROWSEINFO",
	"website" : "https://www.browseinfo.com/demo-request?app=bi_lot_and_serial_expiration_warning_and_restriction&version=19&edition=Community",
	"depends":["base",
			   "sale",
			   "sale_management",
			   "stock",
			   "product_expiry",
			  ],
	"data":[
			"security/access_record_rule.xml",
			],
	'license': 'OPL-1',
    'installable': True,
    'auto_install': False,
    'live_test_url': 'https://www.browseinfo.com/demo-request?app=bi_lot_and_serial_expiration_warning_and_restriction&version=19&edition=Community',
    "images": ['static/description/Banner.gif'],
}
