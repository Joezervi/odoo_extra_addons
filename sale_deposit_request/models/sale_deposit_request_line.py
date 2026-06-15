from odoo import api, fields, models


class SaleDepositRequestLine(models.Model):
    _name = "sale.deposit.request.line"
    _description = "Sales Deposit Request Line"

    deposit_request_id = fields.Many2one(
        "sale.deposit.request",
        required=True,
        ondelete="cascade",
    )

    sale_order_id = fields.Many2one(
        "sale.order",
        required=True,
    )

    sale_order_line_id = fields.Many2one(
        "sale.order.line",
        required=True,
        domain="[('order_id','=',sale_order_id)]",
    )

    partner_id = fields.Many2one(
        related="sale_order_id.partner_id",
        store=True,
    )

    product_id = fields.Many2one(
        "product.product",
        related="sale_order_line_id.product_id",
        store=True,
    )

    qty = fields.Float(
        compute="_compute_values",
        store=True,
    )

    amount = fields.Monetary(
        compute="_compute_values",
        store=True,
    )

    deposit_amount = fields.Monetary(
        compute="_compute_values",
        store=True,
    )

    currency_id = fields.Many2one(
        related="deposit_request_id.currency_id",
        store=True,
    )

    @api.depends(
        "sale_order_line_id",
        "deposit_request_id.deposit_percent",
        "deposit_request_id.deposit_type",
    )
    def _compute_values(self):

        for rec in self:
            line = rec.sale_order_line_id
            rec.qty = line.product_uom_qty
            rec.amount = line.price_subtotal
            if rec.deposit_request_id.deposit_type == "percent":
                rec.deposit_amount = (
                    rec.amount * rec.deposit_request_id.deposit_percent / 100
                )
            else:
                rec.deposit_amount = 0.0
