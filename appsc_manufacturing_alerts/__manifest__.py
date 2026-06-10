{
    "name": "Manufacturing Delay Alerts",
    "version": "19.1",
    "category": "Manufacturing",
    'summary': 'This tool helps factory managers keep track of late manufacturing orders and avoid overloading any shift.'
               ' It shows when production is delayed and warns if too many jobs are assigned to one shift.',
    'description': 'In manufacturing, delays can cause customer dissatisfaction and wasted resources. '
                   'This module automatically calculates how late a production order is and sends alerts when needed. '
                   'It also checks how many open orders are in each shift (A, B, or C) and warns managers if a shift is '
                   'overloaded. This helps improve planning, balance workloads, and meet deadlines.',
    'author': 'AppsComp Widgets Pvt Ltd',
    'company': 'AppsComp Widgets Pvt Ltd',
    'website': 'https://www.appscomp.com',
    'license': 'LGPL-3',
    'images': ['static/description/banner.png'],
    "depends": ["mrp"],
    "data": [
        "views/mrp_production_view.xml"
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
