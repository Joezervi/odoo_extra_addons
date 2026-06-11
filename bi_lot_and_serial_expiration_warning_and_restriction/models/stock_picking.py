# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from datetime import datetime, timedelta
from odoo.exceptions import UserError, ValidationError


class Picking(models.Model):
	_inherit = "stock.picking"

	def button_validate(self):
		res = super(Picking, self).button_validate()
		today = fields.Date.today()
		ir_module_module_obj = self.env['ir.module.module'].search(
			[('name', '=', 'product_expiry'), ('state', '=', 'installed')])
		if ir_module_module_obj:
			if self.env.user.has_group('bi_lot_and_serial_expiration_warning_and_restriction.group_lot_serial_number'):
				stock_picking_obj = self.move_line_ids.lot_id
				for rec in stock_picking_obj:
					if rec.expiration_date:
						stock_production_lot_obj = self.env['stock.lot'].browse([(rec)]).id
						stock_lot_date = stock_production_lot_obj.filtered(lambda x: x.expiration_date and x.expiration_date.date() <= today)
						if stock_lot_date:
							raise ValidationError(
								"This lot is expired you can not use it Please select the another lot number.")
					else:
						raise ValidationError(
							"Please go to Products --> Inventory Section --> Enable the By Lots Selection in Tracking Field --> Enable Expiration Date; After that Input the Expiration Date in Lots/Serial Numbers --> Dates Section")
			else:
				return res
		else:
			raise ValidationError("Please Enable Settings --> Expiration Dates Option.")
		return res