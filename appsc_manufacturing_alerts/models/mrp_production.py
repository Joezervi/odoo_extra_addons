from odoo import models, fields, api, _


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    delay_days = fields.Integer(string="Delay (Days)", compute='_compute_delay_days', store=True)
    shift = fields.Selection([('A', 'Shift A'), ('B', 'Shift B'), ('C', 'Shift C')], string="Shift")

    @api.depends('date_start', 'date_finished')
    def _compute_delay_days(self):
        for rec in self:
            rec.delay_days = 0
            if rec.date_start and rec.date_finished:
                delay = (rec.date_finished.date() - rec.date_start.date()).days
                rec.delay_days = delay
                if delay > 0:
                    rec.message_post(
                        body=_("MO %s has a delay of %s day(s)." % (rec.name, delay))
                    )