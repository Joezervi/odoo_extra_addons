from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ManufactureOrder(models.Model):
    _inherit = "mrp.production"

    @api.model
    def write(self, vals):
        if not self.env.user.has_group('eg_mo_edit_restriction.manufacture_order_edit_restriction'):
            raise UserError(_("You don't have access to Edit Manufacture order."))
        else:
            return super(ManufactureOrder, self).write(vals)
