from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'


    bank_account_number = fields.Char(string="Account Number")
    bank_iban = fields.Char(string="IBAN")
    bank_swift_code = fields.Char(string="SWIFT Code")
    bank_branch_name = fields.Char(string="Branch Name")
    bank_account_type = fields.Selection([
        ('savings', 'Savings'),
        ('current', 'Current'),
        ('cc', 'Cash Credit'),
        ('od', 'Overdraft'),
    ], string="Account Type")
    bank_ifsc_code = fields.Char(string="IFSC Code")