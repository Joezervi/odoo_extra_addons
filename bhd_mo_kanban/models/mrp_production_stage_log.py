from odoo import models, fields, api

class MrpProductionStageLog(models.Model):
    """Log of stage transitions for time tracking"""
    _name = 'mrp.production.stage.log'
    _description = 'MO Stage Transition Log'
    _order = 'create_date desc'

    production_id = fields.Many2one('mrp.production', string='Manufacturing Order',
        required=True, ondelete='cascade', index=True)
    from_stage = fields.Selection([
        ('design', 'Design'),
        ('printing', 'Printing'),
        ('finishing', 'Finishing'),
        ('on_hold', 'On Hold'),
        ('packing', 'Packing'),
        ('done', 'Done'),
        # Legacy values for old records
        ('draft', 'Draft (Legacy)'),
        ('confirmed', 'Confirmed (Legacy)'),
        ('working', 'Working (Legacy)'),
        ('paused', 'Paused (Legacy)'),
    ], string='From Stage', required=True)
    to_stage = fields.Selection([
        ('design', 'Design'),
        ('printing', 'Printing'),
        ('finishing', 'Finishing'),
        ('on_hold', 'On Hold'),
        ('packing', 'Packing'),
        ('done', 'Done'),
        # Legacy values for old records
        ('draft', 'Draft (Legacy)'),
        ('confirmed', 'Confirmed (Legacy)'),
        ('working', 'Working (Legacy)'),
        ('paused', 'Paused (Legacy)'),
    ], string='To Stage', required=True)
    duration_hours = fields.Float(string='Duration (Hours)', digits=(16, 2))
    user_id = fields.Many2one('res.users', string='Changed By',
        default=lambda self: self.env.user)
    notes = fields.Text(string='Notes')

    # Related fields for reporting
    product_id = fields.Many2one(related='production_id.product_id',
        string='Product', store=True)
    partner_id = fields.Many2one(related='production_id.x_partner_id',
        string='Customer', store=True)
