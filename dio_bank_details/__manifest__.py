{
    'name': 'Bank Details in Sale & Invoice',
    'summary': 'Company Bank Details in Sale & Invoice Report',
    'version': '17.0.1.0.0',
    'author': "Diode Info Solutions",
    'website': 'https://www.diodeinfosolutions.com/',
    'category': 'Sale',
    'description': """ This module allows to add bank details in sale and invoice report.""",
    'depends': ['sale','base'],
    'data': [


        'views/res_company.xml',
        'views/sale_report_inherit.xml',
        'views/invoice_report_inherit.xml',

    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'AGPL-3',
}