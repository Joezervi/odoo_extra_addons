from odoo import models, fields, api, _

class StockPicking(models.Model):
    _inherit = "stock.picking"

    stock_request_id = fields.Many2one(comodel_name="hrl.stock.request", string="Stock Request")

class StockMove(models.Model):
    _inherit = "stock.move"

    stock_request_line_id = fields.Many2one(comodel_name="hrl.stock.request.line", string="Stock Request List")