from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    deposit_request_id = fields.Many2one(
        "sale.deposit.request",
        string="Deposit Request",
        copy=False,
    )

    is_deposit_invoice = fields.Boolean(
        string="Deposit Invoice",
        default=False,
        copy=False,
    )

    deposit_applied_amount = fields.Monetary(
        string="Applied Deposit",
        currency_field="currency_id",
    )

    def action_post(self):
        result = super().action_post()
        for move in self.filtered(lambda m: m.is_deposit_invoice):
            request = move.deposit_request_id
            if request:
                request.message_post(body=(f"Deposit Invoice Posted: " f"{move.name}"))

        return result

    @api.model
    def create(self, vals):
        move = super().create(vals)
        if move.deposit_request_id:
            move.message_post(
                body=(f"Linked to Deposit Request " f"{move.deposit_request_id.name}")
            )

        return move

    def action_open_apply_deposit(self):

        self.ensure_one()

        if self.move_type != "out_invoice":
            return

        return {
            "type": "ir.actions.act_window",
            "name": "Apply Deposit",
            "res_model": "sale.deposit.apply.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_invoice_id": self.id,
            },
        }
