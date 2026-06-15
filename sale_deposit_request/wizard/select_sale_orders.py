from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SaleDepositSOSelectionWizard(models.TransientModel):
    _name = "sale.deposit.so.selection.wizard"
    _description = "Select Sales Orders"

    deposit_request_id = fields.Many2one(
        "sale.deposit.request",
        required=True,
    )

    partner_id = fields.Many2one(
        related="deposit_request_id.partner_id",
    )

    sale_order_ids = fields.Many2many(
        "sale.order",
        string="Sales Orders",
        domain="""
            [
                ('partner_id','=',partner_id),
                ('state','in',['sale','done'])
            ]
        """,
    )

    def action_load_so_lines(self):
        self.ensure_one()
        line_obj = self.env["sale.deposit.request.line"]

        for so in self.sale_order_ids:
            for line in so.order_line.filtered(lambda l: not l.display_type):
                exists = line_obj.search(
                    [
                        (
                            "deposit_request_id",
                            "=",
                            self.deposit_request_id.id,
                        ),
                        (
                            "sale_order_line_id",
                            "=",
                            line.id,
                        ),
                    ],
                    limit=1,
                )

                if exists:
                    continue

                line_obj.create(
                    {
                        "deposit_request_id": self.deposit_request_id.id,
                        "sale_order_id": so.id,
                        "sale_order_line_id": line.id,
                    }
                )

        return {"type": "ir.actions.act_window_close"}
