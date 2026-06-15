from odoo import fields, models
from odoo.exceptions import ValidationError


class DepositInvoiceWizard(models.TransientModel):
    _name = "sale.deposit.invoice.wizard"
    _description = "Deposit Invoice Wizard"

    deposit_request_id = fields.Many2one(
        "sale.deposit.request",
        required=True,
    )

    currency_id = fields.Many2one(
        related="deposit_request_id.currency_id"
    )

    available_amount = fields.Monetary(
        compute="_compute_available"
    )

    invoice_amount = fields.Monetary(
        required=True,
    )

    invoice_date = fields.Date(
        default=fields.Date.today
    )

    def _compute_available(self):

        for rec in self:
            rec.available_amount = (
                rec.deposit_request_id.deposit_amount
                - rec.deposit_request_id.invoiced_amount
            )

    def action_create_invoice(self):

        self.ensure_one()

        if self.invoice_amount <= 0:
            raise ValidationError(
                "Invoice amount must be greater than zero."
            )

        if self.invoice_amount > self.available_amount:
            raise ValidationError(
                "Amount exceeds remaining deposit."
            )

        product = self.env.ref(
            "sale_deposit_request.product_customer_deposit"
        )

        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id":
                self.deposit_request_id.partner_id.id,
            "invoice_date":
                self.invoice_date,
            "deposit_request_id":
                self.deposit_request_id.id,
            "is_deposit_invoice":
                True,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id":
                            product.id,
                        "quantity": 1,
                        "price_unit":
                            self.invoice_amount,
                        "name":
                            self.deposit_request_id.name,
                    }
                )
            ]
        })

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": invoice.id,
        }
    
    def action_open_invoice_wizard(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Create Deposit Invoice",
            "res_model":
                "sale.deposit.invoice.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_deposit_request_id":
                    self.id,
            }
        }