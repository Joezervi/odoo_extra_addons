{
    'name': 'BHD MO Kanban - Enhanced',
    'version': '19.0.6.3.0',
    'category': 'Manufacturing',
    'summary': 'Enhanced Kanban board for Manufacturing Orders with visual workflow tracking',
    'description': """
        BHD Manufacturing Order Kanban Board v4.0
        - Redesigned kanban cards with key info at a glance
        - Quick action buttons (Next Stage, Hold, Resume)
        - Progress dots showing pipeline position
        - Deadline tracking with color-coded badges
        - Bidirectional state/stage sync
        - Product short names for readability
        - Worker notes field
        - Improved search and filters
        - Mobile-friendly card design
    """,
    'author': 'BHD Printing',
    'depends': ['mrp', 'sale', 'sale_mrp', 'sale_product_image', 'web', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/notification_templates.xml',
        'data/ir_cron.xml',
        'views/mrp_production_views.xml',
        'views/dashboard_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bhd_mo_kanban/static/src/scss/kanban.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
