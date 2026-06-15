from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleDepositRequest(models.Model):
    _name = "sale.deposit.request"
    _description = "Sales Deposit Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        tracking=True,
    )

    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("sales_approved", "Sales Approved"),
            ("finance_approved", "Finance Approved"),
            ("invoiced", "Invoiced"),
            ("partially_paid", "Partially Paid"),
            ("paid", "Paid"),
            ("partially_applied", "Partially Applied"),
            ("applied", "Applied"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        tracking=True,
    )

    deposit_type = fields.Selection(
        [
            ("percent", "Percentage"),
            ("fixed", "Fixed Amount"),
        ],
        default="percent",
        required=True,
    )

    deposit_percent = fields.Float(
        string="Deposit %",
        default=30.0,
    )

    deposit_amount = fields.Monetary(
        string="Required Deposit",
        compute="_compute_amounts",
        store=True,
    )

    total_amount = fields.Monetary(
        string="Sales Amount",
        compute="_compute_amounts",
        store=True,
    )

    invoiced_amount = fields.Monetary(
        compute="_compute_invoice_amounts",
        store=True,
    )

    paid_amount = fields.Monetary(
        compute="_compute_invoice_amounts",
        store=True,
    )

    balance_amount = fields.Monetary(
        compute="_compute_invoice_amounts",
        store=True,
    )

    line_ids = fields.One2many(
        "sale.deposit.request.line",
        "deposit_request_id",
        string="Sales Lines",
    )

    invoice_ids = fields.One2many(
        "account.move",
        "deposit_request_id",
        string="Deposit Invoices",
    )

    invoice_count = fields.Integer(compute="_compute_counts")

    sale_order_count = fields.Integer(compute="_compute_counts")

    payment_count = fields.Integer(compute="_compute_counts")

    note = fields.Text()

    submitted_by = fields.Many2one(
        "res.users",
        readonly=True,
    )

    submitted_date = fields.Datetime(
        readonly=True,
    )

    sales_approved_by = fields.Many2one(
        "res.users",
        readonly=True,
    )

    sales_approved_date = fields.Datetime(
        readonly=True,
    )

    finance_approved_by = fields.Many2one(
        "res.users",
        readonly=True,
    )

    finance_approved_date = fields.Datetime(
        readonly=True,
    )

    applied_amount = fields.Monetary(
        compute="_compute_applied",
        store=True,
    )

    remaining_amount = fields.Monetary(
        compute="_compute_applied",
        store=True,
    )

    @api.depends("invoice_ids.deposit_applied_amount")
    def _compute_applied(self):
        for rec in self:
            applied = sum(rec.invoice_ids.mapped("deposit_applied_amount"))
            rec.applied_amount = applied
            rec.remaining_amount = rec.paid_amount - applied

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "sale.deposit.request"
                )
        return super().create(vals_list)

    @api.depends(
        "line_ids.amount",
        "deposit_type",
        "deposit_percent",
    )
    def _compute_amounts(self):

        for rec in self:
            total = sum(rec.line_ids.mapped("amount"))
            rec.total_amount = total
            if rec.deposit_type == "percent":
                rec.deposit_amount = total * rec.deposit_percent / 100

    @api.depends(
        "invoice_ids.amount_total",
        "invoice_ids.payment_state",
    )
    def _compute_invoice_amounts(self):

        for rec in self:
            invoiced = sum(
                rec.invoice_ids.filtered(lambda x: x.state == "posted").mapped(
                    "amount_total"
                )
            )

            paid = sum(
                rec.invoice_ids.filtered(
                    lambda x: x.payment_state
                    in (
                        "paid",
                        "in_payment",
                    )
                ).mapped("amount_total")
            )

            rec.invoiced_amount = invoiced
            rec.paid_amount = paid
            rec.balance_amount = rec.deposit_amount - paid

    def _compute_counts(self):
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)
            rec.sale_order_count = len(rec.line_ids.mapped("sale_order_id"))
            rec.payment_count = sum(
                len(inv.line_ids.mapped("matched_credit_ids.credit_move_id"))
                for inv in rec.invoice_ids
            )

    @api.constrains("line_ids")
    def _check_customer(self):

        for rec in self:
            customers = rec.line_ids.mapped("sale_order_id.partner_id")
            if customers and any(partner != rec.partner_id for partner in customers):
                raise ValidationError(
                    _("All Sales Orders must belong to the same customer.")
                )

    @api.constrains("line_ids")
    def _check_so_state(self):

        for rec in self:
            invalid_sos = rec.line_ids.mapped("sale_order_id").filtered(
                lambda so: so.state
                not in (
                    "sale",
                    "done",
                )
            )

            if invalid_sos:
                raise ValidationError(_("Only confirmed Sales Orders are allowed."))

    def action_submit(self):
        self.write(
            {
                "state": "submitted",
                "submitted_by": self.env.user.id,
                "submitted_date": fields.Datetime.now(),
            }
        )

    def action_sales_approve(self):
        self.write(
            {
                "state": "sales_approved",
                "sales_approved_by": self.env.user.id,
                "sales_approved_date": fields.Datetime.now(),
            }
        )

    def action_finance_approve(self):
        self.write(
            {
                "state": "finance_approved",
                "finance_approved_by": self.env.user.id,
                "finance_approved_date": fields.Datetime.now(),
            }
        )

    def action_cancel(self):
        self.state = "cancelled"

    def action_create_invoice(self):
        self.ensure_one()
        if self.deposit_amount <= 0:
            raise ValidationError(_("Deposit amount must be greater than zero."))

        product = self.env.ref("sale_deposit_request.product_customer_deposit")
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_id.id,
                "deposit_request_id": self.id,
                "is_deposit_invoice": True,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "name": self.name,
                            "quantity": 1,
                            "price_unit": self.deposit_amount,
                        },
                    )
                ],
            }
        )

        self.state = "invoiced"

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": invoice.id,
        }

    def action_view_invoices(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Invoices",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [
                (
                    "deposit_request_id",
                    "=",
                    self.id,
                )
            ],
        }

    def action_view_sale_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Sales Orders",
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("id", "in", self.line_ids.mapped("sale_order_id").ids)],
        }

    def action_view_payments(self):
        self.ensure_one()
        payments = self.invoice_ids.mapped(
            "line_ids.matched_credit_ids.credit_move_id.move_id"
        )
        return {
            "type": "ir.actions.act_window",
            "name": "Payments",
            "res_model": "account.payment",
            "view_mode": "list,form",
            "domain": [("id", "in", payments.ids)],
        }
