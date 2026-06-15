from odoo import fields, models
from odoo.exceptions import ValidationError


class SaleDepositApplyWizard(models.TransientModel):
    _name = "sale.deposit.apply.wizard"

    invoice_id = fields.Many2one(
        "account.move",
        required=True,
    )

    deposit_request_id = fields.Many2one(
        "sale.deposit.request",
        required=True,
    )

    available_amount = fields.Monetary(
        related="deposit_request_id.balance_amount"
    )

    apply_amount = fields.Monetary(
        required=True,
    )

    currency_id = fields.Many2one(
        related="invoice_id.currency_id"
    )

    def action_apply(self):
        self.ensure_one()
        if self.apply_amount <= 0:
            raise ValidationError(
                "Amount must be greater than zero."
            )

        if self.apply_amount > self.available_amount:
            raise ValidationError(
                "Amount exceeds available deposit."
            )

        deposit_product = self.env.ref(
            "sale_deposit_request.product_customer_deposit"
        )

        self.invoice_id.write({
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id":
                            deposit_product.id,
                        "name":
                            f"Deposit Applied - "
                            f"{self.deposit_request_id.name}",
                        "quantity": 1,
                        "price_unit":
                            -self.apply_amount,
                    }
                )
            ]
        })

        self.deposit_request_id.message_post(
            body=(
                f"Applied "
                f"{self.apply_amount}"
                f" to invoice "
                f"{self.invoice_id.name}"
            )
        )

        return {
            "type": "ir.actions.act_window_close"
        }